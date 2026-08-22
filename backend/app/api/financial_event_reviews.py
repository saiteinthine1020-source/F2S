"""Workspace-scoped review comments and flags for approved financial events."""

import json
import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.financial_events import _authorization_error, _conflict, _version_error
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.application_support import IdempotencyKeyReused, IdempotencyService
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.household_finance import (
    FinanceCommandMetadata,
    FinancialEventInProgress,
    FinancialEventRecoveryRequired,
    FinancialEventReplayUnavailable,
    FinancialEventReviewRecord,
    FinancialReviewCreateCommand,
    FinancialReviewKind,
    FinancialReviewReason,
    FinancialReviewResolution,
    FinancialReviewService,
    FinancialReviewStateConflict,
    FinancialReviewVersionMismatch,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceVersionMismatch,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint

router = APIRouter(tags=["finance-reviews"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key")]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class FinancialReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: UUID
    kind: FinancialReviewKind
    body: str = Field(min_length=1, max_length=2000)
    reason_code: FinancialReviewReason | None = None


class FinancialReviewResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    resolution_code: FinancialReviewResolution


class FinancialReviewRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    financial_event_id: UUID
    kind: FinancialReviewKind
    body: str
    reason_code: FinancialReviewReason | None
    status: str | None
    author_membership_id: UUID
    created_at: datetime
    resolver_membership_id: UUID | None
    resolved_at: datetime | None
    resolution_code: FinancialReviewResolution | None
    version: int


class FinancialReviewEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: FinancialReviewRepresentation


class FinancialReviewListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: tuple[FinancialReviewRepresentation, ...]


def _service(session: AsyncSession) -> FinancialReviewService:
    return FinancialReviewService(
        SqlAlchemyFinanceRepository(session),
        IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
    )


def _representation(record: FinancialEventReviewRecord) -> FinancialReviewRepresentation:
    return FinancialReviewRepresentation(
        id=record.id,
        financial_event_id=record.financial_event_id,
        kind=FinancialReviewKind(record.review_kind),
        body=record.body_text,
        reason_code=(FinancialReviewReason(record.reason_code) if record.reason_code else None),
        status=record.flag_status,
        author_membership_id=record.created_by_membership_id,
        created_at=record.created_at,
        resolver_membership_id=record.resolved_by_membership_id,
        resolved_at=record.resolved_at,
        resolution_code=(
            FinancialReviewResolution(record.resolution_code) if record.resolution_code else None
        ),
        version=record.version,
    )


def _fingerprint(event_id: UUID, payload: FinancialReviewCreateRequest) -> RequestFingerprint:
    value = json.dumps(
        {"event_id": str(event_id), "payload": payload.model_dump(mode="json")},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return RequestFingerprint.from_canonical_bytes(value)


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise WorkspaceVersionMismatch
    return int(match.group(1))


async def _context(
    session: AsyncSession, request: Request, account_id: UUID, workspace_id: UUID
) -> AuthorizationContext:
    return await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=account_id,
        workspace_id=workspace_id,
        correlation_id=request.state.correlation_id,
    )


async def _audit_permission_denial(session: AsyncSession, context: AuthorizationContext) -> None:
    await SqlAlchemyAuditWriter(session).append(
        AuditEventIntent(
            scope=AuditScope.WORKSPACE,
            workspace_id=context.workspace_id,
            actor=AuditActor.user(context.actor_account_id, context.membership_id),
            action=AuditAction.FINANCE_ACCESS_DENIED,
            module=AuditModule.HOUSEHOLD_FINANCE,
            result=AuditResult.DENIED,
            correlation_id=context.correlation_id,
            resource_type=AuditResourceType.FINANCIAL_EVENT_REVIEW,
            reason=AuditReason.PERMISSION_DENIED,
            source=AuditSource.API,
            context=AuditContext.FINANCE_REVIEW,
        )
    )


@router.get(
    "/api/v1/workspaces/{workspace_id}/financial-events/{event_id}/reviews",
    response_model=FinancialReviewListEnvelope,
)
async def list_financial_event_reviews(
    workspace_id: UUID,
    event_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> FinancialReviewListEnvelope | Response:
    try:
        context = await _context(session, request, account_id, workspace_id)
        records = await _service(session).list_reviews(context, event_id=event_id)
        if records is None:
            return _authorization_error(request, AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND))
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    return FinancialReviewListEnvelope(data=tuple(_representation(row) for row in records))


@router.post(
    "/api/v1/workspaces/{workspace_id}/financial-events/{event_id}/reviews",
    response_model=FinancialReviewEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_financial_event_review(
    workspace_id: UUID,
    event_id: UUID,
    payload: FinancialReviewCreateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> FinancialReviewEnvelope | Response:
    del browser
    try:
        context = await _context(session, request, account_id, workspace_id)
        record, replayed = await _service(session).create(
            context,
            event_id=event_id,
            command=FinancialReviewCreateCommand(payload.kind, payload.body, payload.reason_code),
            metadata=FinanceCommandMetadata(
                payload.operation_id,
                OperationCode("CREATE_FINANCIAL_REVIEW"),
                IdempotencyKey(idempotency_key),
                _fingerprint(event_id, payload),
                Capability.COMMENT_OR_FLAG,
            ),
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except IdempotencyKeyReused:
        return _conflict(request, "IDEMPOTENCY_KEY_REUSED", "The key is already in use.")
    except (FinancialEventInProgress, FinancialEventRecoveryRequired):
        return _conflict(request, "CONFLICT", "The review is already being processed.")
    except FinancialEventReplayUnavailable:
        return _conflict(request, "CONFLICT", "The review cannot be replayed safely.")
    response.headers["Idempotency-Replayed"] = "true" if replayed else "false"
    response.headers["ETag"] = f'"v{record.version}"'
    return FinancialReviewEnvelope(data=_representation(record))


@router.post(
    "/api/v1/workspaces/{workspace_id}/financial-event-reviews/{review_id}/resolutions",
    response_model=FinancialReviewEnvelope,
)
async def resolve_financial_event_review(
    workspace_id: UUID,
    review_id: UUID,
    payload: FinancialReviewResolutionRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> FinancialReviewEnvelope | Response:
    del browser
    expected_version = _expected_version(if_match)
    try:
        context = await _context(session, request, account_id, workspace_id)
        record = await _service(session).resolve(
            context,
            review_id=review_id,
            expected_version=expected_version,
            resolution_code=payload.resolution_code,
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except FinancialReviewVersionMismatch:
        return _version_error(request)
    except FinancialReviewStateConflict:
        return _conflict(request, "INVALID_STATE_TRANSITION", "Only an open flag can be resolved.")
    response.headers["ETag"] = f'"v{record.version}"'
    return FinancialReviewEnvelope(data=_representation(record))
