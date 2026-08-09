"""Fail-closed authentication dependency awaiting the Issue #50 session adapter."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from app.api.bootstrap import Session
from app.infrastructure.database.repositories.sessions import SqlAlchemySessionRepository
from app.modules.identity_security import SecretText
from app.modules.sessions import SessionService


class Unauthenticated(Exception):
    """A safe authentication-boundary failure."""


AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]


async def authenticated_account_id(
    request: Request,
    session: Session,
    authorization: AuthorizationHeader = None,
) -> UUID:
    """Derive the actor from a current opaque access credential and server state."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise Unauthenticated
    value = authorization.removeprefix("Bearer ")
    if not 32 <= len(value) <= 512:
        raise Unauthenticated
    authenticated = await SessionService(
        SqlAlchemySessionRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.dummy_password_digest,
    ).authenticate(
        SecretText(value),
        correlation_id=request.state.correlation_id,
        now=datetime.now(UTC),
    )
    if authenticated is None:
        raise Unauthenticated
    request.state.auth_session_id = authenticated.session_id
    return authenticated.account_id


AuthenticatedAccountId = Annotated[UUID, Depends(authenticated_account_id)]
