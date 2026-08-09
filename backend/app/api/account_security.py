"""Reauthenticated password change and concealed account-recovery HTTP boundary."""

import math
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import safe_error
from app.api.security import AuthenticatedAccountId
from app.infrastructure.database.repositories.account_security import (
    SqlAlchemyAccountSecurityRepository,
)
from app.modules.account_security import (
    AccountSecurityService,
    PasswordChangeAttempt,
    RecoveryConfirmation,
    RecoveryRequest,
)
from app.modules.identity_security import (
    AbuseSubject,
    DigestPurpose,
    SecretText,
    normalize_email,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=15, max_length=1024)


class RecoveryRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=1, max_length=320)


class RecoveryAccepted(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ACCEPTED"] = "ACCEPTED"


class RecoveryAcceptedEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: RecoveryAccepted


class RecoveryConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: SecretStr = Field(min_length=32, max_length=512)
    new_password: SecretStr = Field(min_length=15, max_length=1024)


def service_for(request: Request, session: AsyncSession) -> AccountSecurityService:
    return AccountSecurityService(
        SqlAlchemyAccountSecurityRepository(session, request.app.state.opaque_credentials),
        request.app.state.opaque_credentials,
        request.app.state.password_service,
        request.app.state.recovery_delivery,
    )


def _recovery_subjects(request: Request, email: str) -> tuple[AbuseSubject, AbuseSubject]:
    try:
        identifier = normalize_email(email)
    except ValueError:
        identifier = unicodedata.normalize("NFKC", email).strip().lower()
    network = request.client.host if request.client is not None else "unknown"
    digests = request.app.state.keyed_digests
    return (
        AbuseSubject(
            digests.digest(
                DigestPurpose.RECOVERY_RECIPIENT,
                SecretText(f"recipient:{identifier}"),
            )
        ),
        AbuseSubject(
            digests.digest(
                DigestPurpose.RECOVERY_RECIPIENT,
                SecretText(f"network:{network}"),
            )
        ),
    )


def _recovery_proof_subjects(
    request: Request, value: SecretText
) -> tuple[AbuseSubject, AbuseSubject]:
    network = request.client.host if request.client is not None else "unknown"
    digests = request.app.state.keyed_digests
    return (
        AbuseSubject(
            digests.digest(
                DigestPurpose.RECOVERY_CHALLENGE,
                value,
            )
        ),
        AbuseSubject(
            digests.digest(
                DigestPurpose.RECOVERY_RECIPIENT,
                SecretText(f"network:{network}"),
            )
        ),
    )


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
) -> None | Response:
    del browser
    changed = await service_for(request, session).change_password(
        PasswordChangeAttempt(
            account_id=account_id,
            current_session_id=request.state.auth_session_id,
            current_password=SecretText(payload.current_password.get_secret_value()),
            new_password=SecretText(payload.new_password.get_secret_value()),
            correlation_id=request.state.correlation_id,
            now=datetime.now(UTC),
        )
    )
    if not changed:
        return safe_error(
            status_code=401,
            code="UNAUTHENTICATED",
            message="The current credential is invalid.",
            correlation_id=request.state.correlation_id,
        )
    response.headers["Cache-Control"] = "no-store"
    return None


@router.post(
    "/recovery/request",
    response_model=RecoveryAcceptedEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_recovery(
    payload: RecoveryRequestBody,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
) -> RecoveryAcceptedEnvelope | Response:
    del browser
    now = datetime.now(UTC)
    recipient, network = _recovery_subjects(request, payload.email)
    decision = await request.app.state.recovery_abuse.permit(recipient, network, now=now)
    if not decision.allowed:
        error = safe_error(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many recovery attempts.",
            correlation_id=request.state.correlation_id,
        )
        if decision.retry_after is not None:
            error.headers["Retry-After"] = str(
                max(1, math.ceil(decision.retry_after.total_seconds()))
            )
        return error
    await service_for(request, session).request_recovery(
        RecoveryRequest(payload.email, request.state.correlation_id, now)
    )
    response.headers["Cache-Control"] = "no-store"
    return RecoveryAcceptedEnvelope(data=RecoveryAccepted())


@router.post("/recovery/confirm", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def confirm_recovery(
    payload: RecoveryConfirmationRequest,
    request: Request,
    response: Response,
    session: Session,
    browser: BrowserBoundary,
) -> None | Response:
    del browser
    now = datetime.now(UTC)
    value = SecretText(payload.value.get_secret_value())
    proof, network = _recovery_proof_subjects(request, value)
    decision = await request.app.state.recovery_abuse.permit(proof, network, now=now)
    if not decision.allowed:
        error = safe_error(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many recovery attempts.",
            correlation_id=request.state.correlation_id,
        )
        if decision.retry_after is not None:
            error.headers["Retry-After"] = str(
                max(1, math.ceil(decision.retry_after.total_seconds()))
            )
        return error
    completed = await service_for(request, session).confirm_recovery(
        RecoveryConfirmation(
            value=value,
            new_password=SecretText(payload.new_password.get_secret_value()),
            correlation_id=request.state.correlation_id,
            now=now,
        )
    )
    if not completed:
        return safe_error(
            status_code=401,
            code="UNAUTHENTICATED",
            message="Recovery could not be completed.",
            correlation_id=request.state.correlation_id,
        )
    response.headers["Cache-Control"] = "no-store"
    return None
