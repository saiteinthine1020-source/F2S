"""Admin member provisioning and concealed public activation HTTP boundary."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import safe_error
from app.api.security import AuthenticatedAccountId
from app.infrastructure.database.repositories.member_activation import (
    SqlAlchemyMemberActivationRepository,
)
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.identity_security import SecretText
from app.modules.member_activation import (
    ActivationAttempt,
    MemberActivationService,
    MemberRole,
    ProvisionMemberCommand,
)

router = APIRouter(prefix="/api/v1", tags=["members"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]


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


def service_for(request: Request, session: AsyncSession) -> MemberActivationService:
    return MemberActivationService(
        SqlAlchemyMemberActivationRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.activation_delivery,
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
) -> ProvisionedMemberEnvelope:
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
)
async def restart_activation(
    workspace_id: UUID,
    membership_id: UUID,
    request: Request,
    response: Response,
    actor_account_id: AuthenticatedAccountId,
    session: Session,
) -> None:
    context = await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=actor_account_id,
        workspace_id=workspace_id,
        correlation_id=request.state.correlation_id,
    )
    await service_for(request, session).restart(context, membership_id)
    response.headers["Cache-Control"] = "no-store"


@router.post("/auth/activate", response_model=ActivationEnvelope)
async def activate_account(
    payload: ActivateAccountRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
) -> ActivationEnvelope | Response:
    del browser
    outcome = await service_for(request, session).activate(
        ActivationAttempt(
            value=SecretText(payload.value.get_secret_value()),
            password=(
                SecretText(payload.password.get_secret_value())
                if payload.password is not None
                else None
            ),
            correlation_id=request.state.correlation_id,
            now=datetime.now(UTC),
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
