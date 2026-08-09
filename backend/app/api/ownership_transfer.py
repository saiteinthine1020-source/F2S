"""Reauthenticated, target-confirmed workspace ownership-transfer HTTP boundary."""

import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.member_lifecycle import authorization_error, context_or_error
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.ownership_transfer import (
    SqlAlchemyOwnershipTransferRepository,
)
from app.modules.identity_security import SecretText
from app.modules.ownership_transfer import (
    CancelOwnershipTransfer,
    ConfirmOwnershipTransfer,
    InitiateOwnershipTransfer,
    OwnershipReauthenticationFailed,
    OwnershipTransferConfirmationDenied,
    OwnershipTransferReference,
    OwnershipTransferService,
    OwnershipTransferStateConflict,
    OwnershipTransferStatus,
    OwnershipTransferVersionMismatch,
)
from app.modules.workspace_access import AuthorizationDenied, WorkspaceRole

router = APIRouter(prefix="/api/v1/workspaces", tags=["ownership"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class OwnershipTransferInitiationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_membership_id: UUID
    former_owner_role: Literal[WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR]
    current_password: SecretStr = Field(min_length=1, max_length=1024)


class OwnershipTransferConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: SecretStr = Field(min_length=32, max_length=512)


class EmptyCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OwnershipTransferRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    workspace_id: UUID
    current_owner_membership_id: UUID
    target_membership_id: UUID
    former_owner_role: WorkspaceRole
    status: OwnershipTransferStatus
    expires_at: datetime
    version: int


class OwnershipTransferEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: OwnershipTransferRepresentation


def service_for(request: Request, session: AsyncSession) -> OwnershipTransferService:
    return OwnershipTransferService(
        SqlAlchemyOwnershipTransferRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.ownership_notifications,
    )


def _representation(transfer: OwnershipTransferReference) -> OwnershipTransferRepresentation:
    return OwnershipTransferRepresentation(
        id=transfer.id,
        workspace_id=transfer.workspace_id,
        current_owner_membership_id=transfer.current_owner_membership_id,
        target_membership_id=transfer.target_membership_id,
        former_owner_role=transfer.former_owner_role,
        status=transfer.status,
        expires_at=transfer.expires_at,
        version=transfer.version,
    )


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise OwnershipTransferVersionMismatch
    return int(match.group(1))


def _state_error(request: Request, error: Exception) -> Response:
    if isinstance(error, OwnershipReauthenticationFailed):
        return safe_error(
            status_code=401,
            code="REAUTHENTICATION_REQUIRED",
            message="The current credential is invalid.",
            correlation_id=correlation_for(request),
        )
    if isinstance(error, OwnershipTransferConfirmationDenied):
        return safe_error(
            status_code=401,
            code="TRANSFER_CONFIRMATION_DENIED",
            message="Ownership transfer could not be confirmed.",
            correlation_id=correlation_for(request),
        )
    if isinstance(error, OwnershipTransferVersionMismatch):
        return safe_error(
            status_code=412,
            code="VERSION_MISMATCH",
            message="The resource version is no longer current.",
            correlation_id=correlation_for(request),
        )
    if isinstance(error, OwnershipTransferStateConflict):
        return safe_error(
            status_code=409,
            code="INVALID_STATE_TRANSITION",
            message="The ownership transfer cannot make that state transition.",
            correlation_id=correlation_for(request),
        )
    raise error


@router.post(
    "/{workspace_id}/ownership-transfers",
    response_model=OwnershipTransferEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_ownership_transfer(
    workspace_id: UUID,
    payload: OwnershipTransferInitiationRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
) -> OwnershipTransferEnvelope | Response:
    del browser
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    try:
        transfer = await service_for(request, session).initiate(
            InitiateOwnershipTransfer(
                context=context,
                current_session_id=request.state.auth_session_id,
                target_membership_id=payload.target_membership_id,
                former_owner_role=WorkspaceRole(payload.former_owner_role),
                current_password=SecretText(payload.current_password.get_secret_value()),
                now=datetime.now(UTC),
            )
        )
    except AuthorizationDenied as error:
        return authorization_error(request, error)
    except (OwnershipReauthenticationFailed, OwnershipTransferStateConflict) as error:
        return _state_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"v{transfer.version}"'
    response.headers["Location"] = (
        f"/api/v1/workspaces/{workspace_id}/ownership-transfers/{transfer.id}"
    )
    return OwnershipTransferEnvelope(data=_representation(transfer))


@router.post(
    "/{workspace_id}/ownership-transfers/{transfer_id}/confirm",
    response_model=OwnershipTransferEnvelope,
)
async def confirm_ownership_transfer(
    workspace_id: UUID,
    transfer_id: UUID,
    payload: OwnershipTransferConfirmationRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
) -> OwnershipTransferEnvelope | Response:
    del browser
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    try:
        transfer = await service_for(request, session).confirm(
            ConfirmOwnershipTransfer(
                context=context,
                transfer_id=transfer_id,
                value=SecretText(payload.value.get_secret_value()),
                now=datetime.now(UTC),
            )
        )
    except AuthorizationDenied as error:
        return authorization_error(request, error)
    except OwnershipTransferConfirmationDenied as error:
        return _state_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"v{transfer.version}"'
    return OwnershipTransferEnvelope(data=_representation(transfer))


@router.post(
    "/{workspace_id}/ownership-transfers/{transfer_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def cancel_ownership_transfer(
    workspace_id: UUID,
    transfer_id: UUID,
    payload: EmptyCommandRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> None | Response:
    del payload, browser
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    try:
        await service_for(request, session).cancel(
            CancelOwnershipTransfer(
                context=context,
                transfer_id=transfer_id,
                expected_version=_expected_version(if_match),
                now=datetime.now(UTC),
            )
        )
    except AuthorizationDenied as error:
        return authorization_error(request, error)
    except (OwnershipTransferVersionMismatch, OwnershipTransferStateConflict) as error:
        return _state_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    return None
