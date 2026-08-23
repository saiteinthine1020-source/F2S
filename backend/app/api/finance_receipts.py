"""Private receipt reservation, upload, status, removal, and download API."""

import json
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import (
    BrowserRequest,
    BrowserSecurityDenied,
    require_browser_request,
)
from app.api.errors import correlation_for, safe_error
from app.api.financial_events import _authorization_error, _conflict
from app.api.security import AuthenticatedAccountId
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.database.repositories.receipts import SqlAlchemyReceiptRepository
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyKeyReused,
    IdempotencyService,
    SafeOutcome,
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
    MAX_RECEIPT_BYTES,
    InvalidReceipt,
    ReceiptRecord,
    ReceiptService,
    ReceiptStateConflict,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint

router = APIRouter(tags=["finance-receipts"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]


async def require_binary_browser_request(request: Request) -> BrowserRequest:
    origin = request.headers.get("Origin")
    if origin != request.app.state.settings.frontend_origin:
        raise BrowserSecurityDenied(status_code=403, code="ORIGIN_DENIED")
    assert origin is not None
    media_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if media_type not in {value.value for value in ReceiptMediaType}:
        raise BrowserSecurityDenied(status_code=415, code="UNSUPPORTED_MEDIA_TYPE")
    return BrowserRequest(origin=origin)


BinaryBrowserBoundary = Annotated[BrowserRequest, Depends(require_binary_browser_request)]
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key")]
StrictSha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class ReceiptMediaType(StrEnum):
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"


class ReceiptReserveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: UUID
    filename: str = Field(min_length=1, max_length=128)
    media_type: ReceiptMediaType
    size: int = Field(strict=True, ge=1, le=MAX_RECEIPT_BYTES)
    checksum_sha256: StrictSha256


class ReceiptRemovalReason(StrEnum):
    DUPLICATE = "DUPLICATE"
    WRONG_FILE = "WRONG_FILE"
    REPLACED = "REPLACED"
    OTHER = "OTHER"


class ReceiptRemovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: UUID
    reason_code: ReceiptRemovalReason


class ReceiptRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    financial_event_id: UUID
    state: str
    media_type: ReceiptMediaType
    filename: str
    size: int
    created_at: datetime
    reservation_expires_at: datetime
    failure_code: str | None
    version: int


class ReceiptEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: ReceiptRepresentation


class ReceiptListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: tuple[ReceiptRepresentation, ...]


def _representation(record: ReceiptRecord) -> ReceiptRepresentation:
    return ReceiptRepresentation(
        id=record.id,
        financial_event_id=record.financial_event_id,
        state=record.state,
        media_type=ReceiptMediaType(record.media_type),
        filename=record.filename,
        size=record.expected_size,
        created_at=record.created_at,
        reservation_expires_at=record.expires_at,
        failure_code=record.failure_code,
        version=record.version,
    )


def _service(request: Request, session: AsyncSession) -> ReceiptService:
    return ReceiptService(
        SqlAlchemyReceiptRepository(session),
        request.app.state.receipt_storage,
        request.app.state.receipt_scanner,
    )


async def _context(
    session: AsyncSession, request: Request, account_id: UUID, workspace_id: UUID
) -> AuthorizationContext:
    return await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=account_id,
        workspace_id=workspace_id,
        correlation_id=request.state.correlation_id,
    )


def _fingerprint(values: dict[str, object]) -> RequestFingerprint:
    canonical = json.dumps(values, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return RequestFingerprint.from_canonical_bytes(canonical)


def _invalid(request: Request, code: str) -> Response:
    return safe_error(
        status_code=422,
        code=code,
        message="The receipt does not satisfy the protected-file policy.",
        correlation_id=correlation_for(request),
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
            resource_type=AuditResourceType.PROTECTED_FILE,
            reason=AuditReason.PERMISSION_DENIED,
            source=AuditSource.API,
            context=AuditContext.FINANCE_RECEIPT,
        )
    )


async def _record_permission_denial(
    session: AsyncSession,
    context: AuthorizationContext | None,
    error: AuthorizationDenied,
) -> None:
    if context is not None and error.code is DenialCode.PERMISSION_DENIED:
        await _audit_permission_denial(session, context)


@router.get(
    "/api/v1/workspaces/{workspace_id}/financial-events/{event_id}/receipts",
    response_model=ReceiptListEnvelope,
)
async def list_receipts(
    workspace_id: UUID,
    event_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> ReceiptListEnvelope | Response:
    try:
        context = await _context(session, request, account_id, workspace_id)
        records = await _service(request, session).list(context, event_id=event_id)
        if records is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    return ReceiptListEnvelope(data=tuple(_representation(record) for record in records))


@router.post(
    "/api/v1/workspaces/{workspace_id}/financial-events/{event_id}/receipts",
    response_model=ReceiptEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def reserve_receipt(
    workspace_id: UUID,
    event_id: UUID,
    payload: ReceiptReserveRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> ReceiptEnvelope | Response:
    del browser
    try:
        context = await _context(session, request, account_id, workspace_id)
        idempotency = IdempotencyService(SqlAlchemyIdempotencyRepository(session))
        claim = await idempotency.begin(
            context,
            operation_id=payload.operation_id,
            required_capability=Capability.ATTACH_FINANCE_RECEIPTS,
            operation=OperationCode("RESERVE_FINANCIAL_RECEIPT"),
            key=IdempotencyKey(idempotency_key),
            fingerprint=_fingerprint(
                {"event_id": str(event_id), "payload": payload.model_dump(mode="json")}
            ),
        )
        if claim.disposition is ClaimDisposition.REPLAY:
            outcome = claim.outcome
            if outcome is None or outcome.resource_id is None:
                raise ReceiptStateConflict
            record = await _service(request, session).status(
                context, receipt_id=outcome.resource_id
            )
            if record is None:
                raise ReceiptStateConflict
            replayed = True
        elif claim.disposition is not ClaimDisposition.STARTED:
            raise ReceiptStateConflict
        else:
            record = await _service(request, session).reserve(
                context,
                event_id=event_id,
                operation_id=payload.operation_id,
                filename=payload.filename,
                media_type=payload.media_type.value,
                expected_size=payload.size,
                checksum_sha256=payload.checksum_sha256,
                storage_key=secrets.token_hex(32),
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
            await idempotency.complete(
                context,
                required_capability=Capability.ATTACH_FINANCE_RECEIPTS,
                claim=claim,
                outcome=SafeOutcome(
                    "FINANCIAL_RECEIPT_RESERVED", 201, "PROTECTED_FILE", record.id, record.version
                ),
            )
            replayed = False
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    except IdempotencyKeyReused:
        return _conflict(request, "IDEMPOTENCY_KEY_REUSED", "The key is already in use.")
    except ReceiptStateConflict:
        return _conflict(request, "CONFLICT", "The receipt operation cannot continue.")
    except InvalidReceipt as error:
        return _invalid(request, error.code)
    response.headers["Idempotency-Replayed"] = "true" if replayed else "false"
    response.headers["Location"] = f"/api/v1/workspaces/{workspace_id}/protected-files/{record.id}"
    response.headers["ETag"] = f'"v{record.version}"'
    return ReceiptEnvelope(data=_representation(record))


@router.put(
    "/api/v1/workspaces/{workspace_id}/protected-files/{receipt_id}/content",
    response_model=ReceiptEnvelope,
)
async def upload_receipt_content(
    workspace_id: UUID,
    receipt_id: UUID,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BinaryBrowserBoundary,
) -> ReceiptEnvelope | Response:
    del browser
    length = request.headers.get("content-length")
    if (
        length is None
        or not length.isascii()
        or not length.isdecimal()
        or int(length) > MAX_RECEIPT_BYTES
    ):
        return _invalid(request, "INVALID_FILE_SIZE")
    try:
        context = await _context(session, request, account_id, workspace_id)
        service = _service(request, session)
        content_type = request.headers.get("content-type", "")
        await service.authorize_upload(
            context,
            receipt_id=receipt_id,
            content_type=content_type,
            content_length=int(length),
        )
        content = await request.body()
        record = await service.upload(
            context,
            receipt_id=receipt_id,
            content=content,
            content_type=content_type,
        )
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    except ReceiptStateConflict:
        return _conflict(request, "INVALID_STATE_TRANSITION", "The upload is not eligible.")
    except InvalidReceipt as error:
        return _invalid(request, error.code)
    response.headers["ETag"] = f'"v{record.version}"'
    return ReceiptEnvelope(data=_representation(record))


@router.get(
    "/api/v1/workspaces/{workspace_id}/protected-files/{receipt_id}",
    response_model=ReceiptEnvelope,
)
async def get_receipt_status(
    workspace_id: UUID,
    receipt_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> ReceiptEnvelope | Response:
    try:
        context = await _context(session, request, account_id, workspace_id)
        record = await _service(request, session).status(context, receipt_id=receipt_id)
        if record is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    return ReceiptEnvelope(data=_representation(record))


@router.get("/api/v1/workspaces/{workspace_id}/protected-files/{receipt_id}/download")
async def download_receipt(
    workspace_id: UUID,
    receipt_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> Response:
    try:
        context = await _context(session, request, account_id, workspace_id)
        record, content = await _service(request, session).download(context, receipt_id=receipt_id)
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    except KeyError:
        return _authorization_error(request, AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND))
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{record.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/api/v1/workspaces/{workspace_id}/financial-events/{event_id}/receipts/{receipt_id}/removals",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_receipt(
    workspace_id: UUID,
    event_id: UUID,
    receipt_id: UUID,
    payload: ReceiptRemovalRequest,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> Response:
    del browser
    try:
        context = await _context(session, request, account_id, workspace_id)
        idempotency = IdempotencyService(SqlAlchemyIdempotencyRepository(session))
        claim = await idempotency.begin(
            context,
            operation_id=payload.operation_id,
            required_capability=Capability.ATTACH_FINANCE_RECEIPTS,
            operation=OperationCode("REMOVE_FINANCIAL_RECEIPT"),
            key=IdempotencyKey(idempotency_key),
            fingerprint=_fingerprint(
                {
                    "event_id": str(event_id),
                    "receipt_id": str(receipt_id),
                    "payload": payload.model_dump(mode="json"),
                }
            ),
        )
        if claim.disposition is ClaimDisposition.STARTED:
            await _service(request, session).remove(
                context,
                event_id=event_id,
                receipt_id=receipt_id,
                operation_id=payload.operation_id,
                reason_code=payload.reason_code.value,
            )
            await idempotency.complete(
                context,
                required_capability=Capability.ATTACH_FINANCE_RECEIPTS,
                claim=claim,
                outcome=SafeOutcome("FINANCIAL_RECEIPT_REMOVED", 204),
            )
        elif claim.disposition is not ClaimDisposition.REPLAY:
            raise ReceiptStateConflict
    except AuthorizationDenied as error:
        await _record_permission_denial(session, locals().get("context"), error)
        return _authorization_error(request, error)
    except IdempotencyKeyReused:
        return _conflict(request, "IDEMPOTENCY_KEY_REUSED", "The key is already in use.")
    except ReceiptStateConflict:
        return _conflict(request, "INVALID_STATE_TRANSITION", "The receipt is not removable.")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
