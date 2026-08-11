"""Framework-free opaque login and rotating-session orchestration."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.modules.identity_security import (
    AbuseSubject,
    Argon2idPasswordService,
    IssuedOpaqueCredential,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretText,
    SubjectAbuseControl,
    normalize_email,
)

ACCESS_LIFETIME = timedelta(minutes=15)
REFRESH_IDLE_LIFETIME = timedelta(days=7)
ABSOLUTE_SESSION_LIFETIME = timedelta(days=30)


class LogoutScope(StrEnum):
    CURRENT = "CURRENT"
    ALL = "ALL"


@dataclass(frozen=True, slots=True)
class LoginCandidate:
    account_id: UUID
    password_digest: PasswordDigest
    active: bool


@dataclass(frozen=True, slots=True)
class SessionCredentialBundle:
    access: IssuedOpaqueCredential
    refresh: IssuedOpaqueCredential
    csrf: IssuedOpaqueCredential
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access: SecretText
    refresh: SecretText
    csrf: SecretText
    access_expires_at: datetime
    refresh_expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class LoginAttempt:
    email: str
    password: SecretText
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class RotationAttempt:
    refresh: SecretText
    csrf: SecretText
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class LogoutAttempt:
    refresh: SecretText
    csrf: SecretText
    scope: LogoutScope
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class RotationLease:
    parent_session_id: UUID
    account_id: UUID
    family_id: UUID
    absolute_expires_at: datetime


class RefreshRateLimited(Exception):
    """Safe refresh throttle result without session or counter detail."""

    def __init__(self, retry_after: timedelta | None) -> None:
        self.retry_after = retry_after
        super().__init__("RATE_LIMITED")


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    account_id: UUID
    session_id: UUID


class SessionRepository(Protocol):
    async def login_candidate(self, normalized_email: str | None) -> LoginCandidate | None: ...

    async def login_failed(self, correlation_id: UUID) -> None: ...

    async def create_session(
        self,
        account_id: UUID,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
        replacement_password_digest: PasswordDigest | None,
    ) -> None: ...

    async def prepare_rotation(self, attempt: RotationAttempt) -> RotationLease | None: ...

    async def complete_rotation(
        self,
        lease: RotationLease,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
    ) -> None: ...

    async def authenticate_access(
        self, access: SecretText, *, now: datetime, correlation_id: UUID
    ) -> AuthenticatedSession | None: ...

    async def logout(self, attempt: LogoutAttempt) -> None: ...


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        credentials: OpaqueCredentialService,
        passwords: Argon2idPasswordService,
        dummy_password_digest: PasswordDigest,
        refresh_abuse: SubjectAbuseControl | None = None,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._passwords = passwords
        self._dummy_password_digest = dummy_password_digest
        self._refresh_abuse = refresh_abuse

    async def login(self, attempt: LoginAttempt) -> SessionTokens | None:
        normalized_email: str | None
        try:
            normalized_email = normalize_email(attempt.email)
        except ValueError:
            normalized_email = None
        candidate = await self._repository.login_candidate(normalized_email)
        expected = (
            candidate.password_digest if candidate is not None else self._dummy_password_digest
        )
        verification = self._passwords.verify(attempt.password, expected)
        if candidate is None or not candidate.active or not verification.matches:
            await self._repository.login_failed(attempt.correlation_id)
            return None

        replacement = (
            self._passwords.rehash_verified(attempt.password) if verification.needs_rehash else None
        )
        absolute = attempt.now + ABSOLUTE_SESSION_LIFETIME
        bundle = self._issue_bundle(attempt.now, absolute)
        await self._repository.create_session(
            candidate.account_id,
            bundle,
            attempt.correlation_id,
            replacement,
        )
        return _tokens(bundle)

    async def rotate(self, attempt: RotationAttempt) -> SessionTokens | None:
        lease = await self._repository.prepare_rotation(attempt)
        if lease is None:
            return None
        if self._refresh_abuse is not None:
            family_subject = AbuseSubject(
                self._credentials.fingerprint(
                    OpaqueCredentialPurpose.REFRESH_CREDENTIAL,
                    SecretText(f"family:{lease.family_id}"),
                )
            )
            decision = await self._refresh_abuse.permit(family_subject, now=attempt.now)
            if not decision.allowed:
                raise RefreshRateLimited(decision.retry_after)
        bundle = self._issue_bundle(attempt.now, lease.absolute_expires_at)
        await self._repository.complete_rotation(
            lease,
            bundle,
            attempt.correlation_id,
        )
        return _tokens(bundle)

    async def authenticate(
        self,
        access: SecretText,
        *,
        correlation_id: UUID,
        now: datetime | None = None,
    ) -> AuthenticatedSession | None:
        return await self._repository.authenticate_access(
            access,
            now=now or datetime.now(UTC),
            correlation_id=correlation_id,
        )

    async def logout(self, attempt: LogoutAttempt) -> None:
        await self._repository.logout(attempt)

    def _issue_bundle(
        self, issued_at: datetime, absolute_expires_at: datetime
    ) -> SessionCredentialBundle:
        access_lifetime = min(ACCESS_LIFETIME, absolute_expires_at - issued_at)
        refresh_lifetime = min(REFRESH_IDLE_LIFETIME, absolute_expires_at - issued_at)
        if access_lifetime <= timedelta(0) or refresh_lifetime <= timedelta(0):
            raise ValueError("SESSION_EXPIRED")
        return SessionCredentialBundle(
            access=self._credentials.issue(
                OpaqueCredentialPurpose.ACCESS_CREDENTIAL,
                now=issued_at,
                lifetime=access_lifetime,
            ),
            refresh=self._credentials.issue(
                OpaqueCredentialPurpose.REFRESH_CREDENTIAL,
                now=issued_at,
                lifetime=refresh_lifetime,
            ),
            csrf=self._credentials.issue(
                OpaqueCredentialPurpose.CSRF_CREDENTIAL,
                now=issued_at,
                lifetime=refresh_lifetime,
            ),
            absolute_expires_at=absolute_expires_at,
        )


def _tokens(bundle: SessionCredentialBundle) -> SessionTokens:
    return SessionTokens(
        access=bundle.access.value,
        refresh=bundle.refresh.value,
        csrf=bundle.csrf.value,
        access_expires_at=bundle.access.record.expires_at,
        refresh_expires_at=bundle.refresh.record.expires_at,
        absolute_expires_at=bundle.absolute_expires_at,
    )
