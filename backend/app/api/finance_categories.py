"""Workspace-scoped finance-category HTTP contracts."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
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
    ActivityClassification,
    CategoryApplicability,
    DuplicateFinanceCategory,
    FinanceCategoryRecord,
    FinanceCategoryService,
    FinanceCategoryStateConflict,
    FinanceCategoryVersionMismatch,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceVersionMismatch,
)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/finance-categories", tags=["finance"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class FinanceCategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    applicability: CategoryApplicability
    activity_classification: ActivityClassification | None = None


class FinanceCategoryRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)


class FinanceCategoryArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FinanceCategoryRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    applicability: CategoryApplicability
    activity_classification: ActivityClassification | None
    status: str
    version: int


class FinanceCategoryEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: FinanceCategoryRepresentation


class FinanceCategoryListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: tuple[FinanceCategoryRepresentation, ...]


def _service(session: AsyncSession) -> FinanceCategoryService:
    return FinanceCategoryService(SqlAlchemyFinanceRepository(session))


def _representation(record: FinanceCategoryRecord) -> FinanceCategoryRepresentation:
    return FinanceCategoryRepresentation(
        id=record.id,
        name=record.display_name,
        applicability=CategoryApplicability(record.applicability_code),
        activity_classification=(
            ActivityClassification(record.activity_classification_code)
            if record.activity_classification_code is not None
            else None
        ),
        status=record.status,
        version=record.version,
    )


def _etag(version: int) -> str:
    return f'"v{version}"'


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise WorkspaceVersionMismatch
    return int(match.group(1))


def _authorization_error(request: Request, error: AuthorizationDenied) -> Response:
    not_found = error.code is DenialCode.RESOURCE_NOT_FOUND
    return safe_error(
        status_code=404 if not_found else 403,
        code="RESOURCE_NOT_FOUND" if not_found else "PERMISSION_DENIED",
        message=(
            "The requested resource was not found."
            if not_found
            else "The operation is not permitted."
        ),
        correlation_id=correlation_for(request),
    )


async def _resolve_context(
    session: AsyncSession,
    *,
    account_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
) -> AuthorizationContext:
    return await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=account_id,
        workspace_id=workspace_id,
        correlation_id=correlation_id,
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
            resource_type=AuditResourceType.FINANCE_CATEGORY,
            reason=AuditReason.PERMISSION_DENIED,
            source=AuditSource.API,
            context=AuditContext.FINANCE_ENTRY,
        )
    )


@router.get("", response_model=FinanceCategoryListEnvelope)
async def list_finance_categories(
    workspace_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
    include_archived: Annotated[bool, Query()] = False,
) -> FinanceCategoryListEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        records = await _service(session).list_categories(
            context, include_archived=include_archived
        )
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    return FinanceCategoryListEnvelope(data=tuple(_representation(item) for item in records))


@router.post("", response_model=FinanceCategoryEnvelope, status_code=status.HTTP_201_CREATED)
async def create_finance_category(
    workspace_id: UUID,
    payload: FinanceCategoryCreateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
) -> FinanceCategoryEnvelope | Response:
    del browser
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record = await _service(session).create(
            context,
            name=payload.name,
            applicability=payload.applicability,
            activity=payload.activity_classification,
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except DuplicateFinanceCategory:
        return _conflict(request, "DUPLICATE_RESOURCE", "An active category already exists.")
    response.headers["ETag"] = _etag(record.version)
    return FinanceCategoryEnvelope(data=_representation(record))


@router.patch("/{category_id}", response_model=FinanceCategoryEnvelope)
async def rename_finance_category(
    workspace_id: UUID,
    category_id: UUID,
    payload: FinanceCategoryRenameRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> FinanceCategoryEnvelope | Response:
    del browser
    expected_version = _expected_version(if_match)
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record = await _service(session).rename(
            context,
            category_id=category_id,
            expected_version=expected_version,
            name=payload.name,
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except DuplicateFinanceCategory:
        return _conflict(request, "DUPLICATE_RESOURCE", "An active category already exists.")
    except FinanceCategoryVersionMismatch:
        return _version_error(request)
    except FinanceCategoryStateConflict:
        return _conflict(request, "INVALID_STATE_TRANSITION", "The category is archived.")
    response.headers["ETag"] = _etag(record.version)
    return FinanceCategoryEnvelope(data=_representation(record))


@router.post("/{category_id}/archivals", response_model=FinanceCategoryEnvelope)
async def archive_finance_category(
    workspace_id: UUID,
    category_id: UUID,
    payload: FinanceCategoryArchiveRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> FinanceCategoryEnvelope | Response:
    del payload, browser
    expected_version = _expected_version(if_match)
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record = await _service(session).archive(
            context, category_id=category_id, expected_version=expected_version
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except FinanceCategoryVersionMismatch:
        return _version_error(request)
    except FinanceCategoryStateConflict:
        return _conflict(request, "INVALID_STATE_TRANSITION", "The category is archived.")
    response.headers["ETag"] = _etag(record.version)
    return FinanceCategoryEnvelope(data=_representation(record))


def _version_error(request: Request) -> Response:
    return safe_error(
        status_code=412,
        code="VERSION_MISMATCH",
        message="The resource version is no longer current.",
        correlation_id=correlation_for(request),
    )


def _conflict(request: Request, code: str, message: str) -> Response:
    return safe_error(
        status_code=409,
        code=code,
        message=message,
        correlation_id=correlation_for(request),
    )
