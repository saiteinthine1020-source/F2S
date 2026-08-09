"""One-time installation bootstrap HTTP boundary."""

from collections.abc import AsyncIterator
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.repositories.bootstrap import SqlAlchemyBootstrapRepository
from app.infrastructure.database.session import transactional_session
from app.modules.bootstrap.service import BootstrapCommand, BootstrapService
from app.modules.identity_security import Argon2idPasswordService, SecretText
from app.modules.workspace_access import WorkspaceType

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])


class BootstrapAvailability(BaseModel):
    model_config = ConfigDict(frozen=True)
    available: bool


class BootstrapAvailabilityEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: BootstrapAvailability


class BootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=15, max_length=1024)
    account_language: Literal["en", "ja", "my", "shn"]
    account_timezone: str = Field(min_length=1, max_length=64)
    workspace_name: str = Field(min_length=1, max_length=160)
    workspace_type: WorkspaceType
    base_currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    workspace_language: Literal["en", "ja", "my", "shn"]
    workspace_timezone: str = Field(min_length=1, max_length=64)


class BootstrapRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)
    account_id: UUID
    workspace_id: UUID
    membership_id: UUID
    status: Literal["COMPLETE"] = "COMPLETE"


class BootstrapEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    data: BootstrapRepresentation


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with transactional_session(factory) as session:
        yield session


Session = Annotated[AsyncSession, Depends(database_session)]


def service_for(session: AsyncSession) -> BootstrapService:
    return BootstrapService(
        SqlAlchemyBootstrapRepository(session),
        Argon2idPasswordService(),
    )


@router.get("/bootstrap", response_model=BootstrapAvailabilityEnvelope)
async def bootstrap_availability(
    response: Response, session: Session
) -> BootstrapAvailabilityEnvelope:
    response.headers["Cache-Control"] = "no-store"
    available = await service_for(session).is_available()
    return BootstrapAvailabilityEnvelope(data=BootstrapAvailability(available=available))


@router.post(
    "/bootstrap",
    response_model=BootstrapEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def complete_bootstrap(
    request: Request,
    response: Response,
    payload: BootstrapRequest,
    session: Session,
) -> BootstrapEnvelope:
    response.headers["Cache-Control"] = "no-store"
    result = await service_for(session).complete(
        BootstrapCommand(
            display_name=payload.display_name,
            email=payload.email,
            password=SecretText(payload.password.get_secret_value()),
            account_language=payload.account_language,
            account_timezone=payload.account_timezone,
            workspace_name=payload.workspace_name,
            workspace_type=payload.workspace_type,
            base_currency_code=payload.base_currency_code,
            workspace_language=payload.workspace_language,
            workspace_timezone=payload.workspace_timezone,
            correlation_id=request.state.correlation_id,
        )
    )
    response.headers["Location"] = f"/api/v1/workspaces/{result.workspace_id}"
    return BootstrapEnvelope(
        data=BootstrapRepresentation(
            account_id=result.account_id,
            workspace_id=result.workspace_id,
            membership_id=result.membership_id,
        )
    )
