"""Admin member provisioning and concealed public activation HTTP boundary."""

import math
import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import safe_error
from app.api.member_lifecycle import audit_denial, authorization_error, context_or_error
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.member_activation import (
    SqlAlchemyMemberActivationRepository,
)
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.audit import AuditAction, AuditReason
from app.modules.identity_security import AbuseSubject, DigestPurpose, SecretText
from app.modules.member_activation import (
    ActivationAttempt,
    MemberActivationService,
    MemberRole,
    ProvisionMemberCommand,
)
from app.modules.member_lifecycle import MemberVersionMismatch
from app.modules.workspace_access import AuthorizationContext, AuthorizationDenied, DenialCode

router = APIRouter(prefix="/api/v1", tags=["members"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class ProvisionMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    role: MemberRole
    preferred_language: Literal["en", "ja", "my", "shn"]
    timezone: str = Field(min_length=1, max_length=64)


class ProvisionedMemberRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    role: MemberRole
    status: Literal["PENDING"] = "PENDING"


class ProvisionedMemberEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: ProvisionedMemberRepresentation


class ActivateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: SecretStr = Field(min_length=32, max_length=512)
    password: SecretStr | None = Field(default=None, min_length=15, max_length=1024)


class ActivationRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ACTIVE"] = "ACTIVE"


class ActivationEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: ActivationRepresentation


class RestartActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise MemberVersionMismatch
    return int(match.group(1))


def service_for(request: Request, session: AsyncSession) -> MemberActivationService:
    return MemberActivationService(
        SqlAlchemyMemberActivationRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.activation_delivery,
    )


def _activation_subjects(request: Request, value: SecretText) -> tuple[AbuseSubject, AbuseSubject]:
    network = request.client.host if request.client is not None else "unknown"
    digests = request.app.state.keyed_digests
    return (
        AbuseSubject(digests.digest(DigestPurpose.ACTIVATION_CHALLENGE, value)),
        AbuseSubject(
            digests.digest(
                DigestPurpose.ACTIVATION_CHALLENGE,
                SecretText(f"network:{network}"),
            )
        ),
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=ProvisionedMemberEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def provision_member(
    workspace_id: UUID,
    payload: ProvisionMemberRequest,
    request: Request,
    response: Response,
    actor_account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
) -> ProvisionedMemberEnvelope:
    del browser
    context = await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=actor_account_id,
        workspace_id=workspace_id,
        correlation_id=request.state.correlation_id,
    )
    result = await service_for(request, session).provision(
        ProvisionMemberCommand(
            context=context,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            preferred_language=payload.preferred_language,
            timezone=payload.timezone,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = (
        f"/api/v1/workspaces/{workspace_id}/members/{result.membership_id}"
    )
    return ProvisionedMemberEnvelope(
        data=ProvisionedMemberRepresentation(id=result.membership_id, role=result.role)
    )


@router.post(
    "/workspaces/{workspace_id}/members/{membership_id}/activation/restart",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def restart_activation(
    workspace_id: UUID,
    membership_id: UUID,
    payload: RestartActivationRequest,
    request: Request,
    response: Response,
    actor_account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> None | Response:
    del payload, browser
    expected_version = _expected_version(if_match)
    resolved = await context_or_error(request, session, actor_account_id, workspace_id)
    if isinstance(resolved, Response):
        return resolved
    context: AuthorizationContext = resolved
    try:
        version = await service_for(request, session).restart(
            context, membership_id, expected_version=expected_version
        )
    except AuthorizationDenied as error:
        await audit_denial(
            session,
            context,
            AuditAction.ACTIVATION_RESTARTED,
            (
                AuditReason.RESOURCE_NOT_FOUND
                if error.code is DenialCode.RESOURCE_NOT_FOUND
                else AuditReason.PERMISSION_DENIED
            ),
        )
        return authorization_error(request, error)
    except MemberVersionMismatch:
        return safe_error(
            status_code=412,
            code="VERSION_MISMATCH",
            message="The resource version is no longer current.",
            correlation_id=request.state.correlation_id,
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = f'"v{version}"'
    return None


@router.post("/auth/activate", response_model=ActivationEnvelope)
async def activate_account(
    payload: ActivateAccountRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
) -> ActivationEnvelope | Response:
    del browser
    now = datetime.now(UTC)
    activation_value = SecretText(payload.value.get_secret_value())
    subject, network = _activation_subjects(request, activation_value)
    decision = await request.app.state.activation_abuse.permit(subject, network, now=now)
    if not decision.allowed:
        error = safe_error(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many activation attempts.",
            correlation_id=request.state.correlation_id,
        )
        if decision.retry_after is not None:
            error.headers["Retry-After"] = str(
                max(1, math.ceil(decision.retry_after.total_seconds()))
            )
        return error
    outcome = await service_for(request, session).activate(
        ActivationAttempt(
            value=activation_value,
            password=(
                SecretText(payload.password.get_secret_value())
                if payload.password is not None
                else None
            ),
            correlation_id=request.state.correlation_id,
            now=now,
        )
    )
    if not outcome.activated:
        return safe_error(
            status_code=401,
            code="UNAUTHENTICATED",
            message="Activation could not be completed.",
            correlation_id=request.state.correlation_id,
        )
    response.headers["Cache-Control"] = "no-store"
    return ActivationEnvelope(data=ActivationRepresentation())
