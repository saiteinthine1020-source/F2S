"""Concealed login, rotating refresh, and idempotent logout HTTP boundary."""

import math
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import safe_error
from app.infrastructure.database.repositories.sessions import SqlAlchemySessionRepository
from app.modules.identity_security import (
    AbuseSubject,
    DigestPurpose,
    SecretText,
    normalize_email,
)
from app.modules.sessions import (
    LoginAttempt,
    LogoutAttempt,
    LogoutScope,
    RotationAttempt,
    SessionService,
    SessionTokens,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
REFRESH_COOKIE = "__Host-f2s_refresh"

BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]
CsrfHeader = Annotated[str | None, Header(alias="X-CSRF-Token")]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=1, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: LogoutScope = LogoutScope.CURRENT


class SessionRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    csrf_token: str
    token_type: Literal["Bearer"] = "Bearer"
    access_expires_at: datetime
    absolute_expires_at: datetime


class SessionEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: SessionRepresentation


def service_for(request: Request, session: AsyncSession) -> SessionService:
    return SessionService(
        SqlAlchemySessionRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.dummy_password_digest,
    )


def _session_response(response: Response, tokens: SessionTokens) -> SessionEnvelope:
    max_age = max(0, int((tokens.refresh_expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens.refresh.reveal(),
        max_age=max_age,
        expires=tokens.refresh_expires_at,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionEnvelope(
        data=SessionRepresentation(
            access_token=tokens.access.reveal(),
            csrf_token=tokens.csrf.reveal(),
            access_expires_at=tokens.access_expires_at,
            absolute_expires_at=tokens.absolute_expires_at,
        )
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def _session_error(request: Request, message: str) -> Response:
    error = safe_error(
        status_code=401,
        code="UNAUTHENTICATED",
        message=message,
        correlation_id=request.state.correlation_id,
    )
    _clear_refresh_cookie(error)
    return error


def _presented(value: str | None) -> SecretText | None:
    if value is None or not 32 <= len(value) <= 512:
        return None
    return SecretText(value)


def _login_subjects(request: Request, email: str) -> tuple[AbuseSubject, AbuseSubject]:
    try:
        identifier = normalize_email(email)
    except ValueError:
        identifier = unicodedata.normalize("NFKC", email).strip().lower()
    network = request.client.host if request.client is not None else "unknown"
    digests = request.app.state.keyed_digests
    account_subject = AbuseSubject(
        digests.digest(DigestPurpose.LOGIN_IDENTIFIER, SecretText(f"account:{identifier}"))
    )
    network_subject = AbuseSubject(
        digests.digest(DigestPurpose.LOGIN_IDENTIFIER, SecretText(f"network:{network}"))
    )
    return account_subject, network_subject


@router.post("/login", response_model=SessionEnvelope)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
) -> SessionEnvelope | Response:
    del browser
    now = datetime.now(UTC)
    account_subject, network_subject = _login_subjects(request, payload.email)
    decision = await request.app.state.login_abuse.permit(
        account_subject,
        network_subject,
        now=now,
    )
    if not decision.allowed:
        error = safe_error(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many authentication attempts.",
            correlation_id=request.state.correlation_id,
        )
        if decision.retry_after is not None:
            error.headers["Retry-After"] = str(
                max(1, math.ceil(decision.retry_after.total_seconds()))
            )
        return error
    tokens = await service_for(request, session).login(
        LoginAttempt(
            email=payload.email,
            password=SecretText(payload.password.get_secret_value()),
            correlation_id=request.state.correlation_id,
            now=now,
        )
    )
    if tokens is None:
        await request.app.state.login_abuse.failed(account_subject, now=now)
        return _session_error(request, "The credentials are invalid.")
    await request.app.state.login_abuse.succeeded(account_subject)
    return _session_response(response, tokens)


@router.post("/refresh", response_model=SessionEnvelope)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
    refresh_cookie: RefreshCookie = None,
    csrf_header: CsrfHeader = None,
) -> SessionEnvelope | Response:
    del payload, browser
    refresh_value, csrf_value = _presented(refresh_cookie), _presented(csrf_header)
    if refresh_value is None or csrf_value is None:
        return _session_error(request, "The session is unavailable.")
    tokens = await service_for(request, session).rotate(
        RotationAttempt(
            refresh=refresh_value,
            csrf=csrf_value,
            correlation_id=request.state.correlation_id,
            now=datetime.now(UTC),
        )
    )
    if tokens is None:
        return _session_error(request, "The session is unavailable.")
    return _session_response(response, tokens)


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
    refresh_cookie: RefreshCookie = None,
    csrf_header: CsrfHeader = None,
) -> None:
    del browser
    refresh_value, csrf_value = _presented(refresh_cookie), _presented(csrf_header)
    if refresh_value is not None and csrf_value is not None:
        await service_for(request, session).logout(
            LogoutAttempt(
                refresh=refresh_value,
                csrf=csrf_value,
                scope=payload.scope,
                correlation_id=request.state.correlation_id,
                now=datetime.now(UTC),
            )
        )
    _clear_refresh_cookie(response)
