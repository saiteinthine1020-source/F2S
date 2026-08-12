"""Opaque-session service issuance, concealment, and lifetime tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.identity_security import (
    Argon2idPasswordService,
    DevelopmentSubjectAbuseControl,
    KeyedDigestService,
    OpaqueCredentialService,
    PasswordDigest,
    SecretBytes,
    SecretText,
)
from app.modules.sessions import (
    ABSOLUTE_SESSION_LIFETIME,
    ACCESS_LIFETIME,
    REFRESH_IDLE_LIFETIME,
    AuthenticatedSession,
    LoginAttempt,
    LoginCandidate,
    LogoutAttempt,
    RefreshRateLimited,
    RotationAttempt,
    RotationLease,
    SessionCredentialBundle,
    SessionRepository,
    SessionService,
)


class CapturingSessionRepository(SessionRepository):
    def __init__(self, candidate: LoginCandidate | None = None) -> None:
        self.candidate = candidate
        self.failed = 0
        self.bundle: SessionCredentialBundle | None = None
        self.replacement: PasswordDigest | None = None
        self.normalized_email: str | None = "not-called"
        self.rotation_lease: RotationLease | None = None

    async def login_candidate(self, normalized_email: str | None) -> LoginCandidate | None:
        self.normalized_email = normalized_email
        return self.candidate

    async def login_failed(self, correlation_id: UUID) -> None:
        del correlation_id
        self.failed += 1

    async def create_session(
        self,
        account_id: UUID,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
        replacement_password_digest: PasswordDigest | None,
    ) -> None:
        del account_id, correlation_id
        self.bundle = bundle
        self.replacement = replacement_password_digest

    async def prepare_rotation(self, attempt: RotationAttempt) -> RotationLease | None:
        del attempt
        return self.rotation_lease

    async def complete_rotation(
        self,
        lease: RotationLease,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
    ) -> None:
        del lease, correlation_id
        self.bundle = bundle

    async def authenticate_access(
        self, access: SecretText, *, now: datetime, correlation_id: UUID
    ) -> AuthenticatedSession | None:
        del access, now, correlation_id
        return AuthenticatedSession(uuid4(), uuid4())

    async def logout(self, attempt: LogoutAttempt) -> None:
        del attempt


def _credentials() -> OpaqueCredentialService:
    return OpaqueCredentialService(
        KeyedDigestService(SecretBytes(b"synthetic-session-service-test-key"))
    )


def _services(
    repository: CapturingSessionRepository,
) -> tuple[SessionService, Argon2idPasswordService]:
    passwords = Argon2idPasswordService()
    dummy = passwords.hash(SecretText("synthetic-dummy-password"))
    return SessionService(repository, _credentials(), passwords, dummy), passwords


def test_valid_login_issues_independent_redacted_credentials_with_bounded_lifetimes() -> None:
    account_id = uuid4()
    repository = CapturingSessionRepository()
    service, passwords = _services(repository)
    repository.candidate = LoginCandidate(
        account_id,
        passwords.hash(SecretText("synthetic-valid-password")),
        True,
    )
    now = datetime(2026, 8, 9, tzinfo=UTC)

    tokens = asyncio.run(
        service.login(
            LoginAttempt(
                " USER@Example.Invalid ",
                SecretText("synthetic-valid-password"),
                uuid4(),
                now,
            )
        )
    )

    assert tokens is not None
    assert repository.normalized_email == "user@example.invalid"
    assert repository.bundle is not None
    values = {tokens.access.reveal(), tokens.refresh.reveal(), tokens.csrf.reveal()}
    assert len(values) == 3
    assert tokens.access_expires_at == now + ACCESS_LIFETIME
    assert tokens.refresh_expires_at == now + REFRESH_IDLE_LIFETIME
    assert tokens.absolute_expires_at == now + ABSOLUTE_SESSION_LIFETIME
    assert all(value not in repr(tokens) for value in values)
    persisted = {
        repository.bundle.access.record.digest.for_persistence(),
        repository.bundle.refresh.record.digest.for_persistence(),
        repository.bundle.csrf.record.digest.for_persistence(),
    }
    assert values.isdisjoint(persisted)


def test_unknown_invalid_and_inactive_login_are_concealed() -> None:
    for email, candidate in (
        ("missing@example.invalid", None),
        ("not-an-email", None),
        (
            "inactive@example.invalid",
            LoginCandidate(uuid4(), PasswordDigest("malformed-verifier"), False),
        ),
    ):
        repository = CapturingSessionRepository(candidate)
        service, _ = _services(repository)
        outcome = asyncio.run(
            service.login(
                LoginAttempt(
                    email,
                    SecretText("synthetic-invalid-password"),
                    uuid4(),
                    datetime.now(UTC),
                )
            )
        )
        assert outcome is None
        assert repository.failed == 1
        assert repository.bundle is None


def test_rotation_never_extends_absolute_expiry() -> None:
    repository = CapturingSessionRepository()
    service, _ = _services(repository)
    now = datetime(2026, 8, 29, tzinfo=UTC)
    absolute = now + timedelta(hours=1)
    repository.rotation_lease = RotationLease(uuid4(), uuid4(), uuid4(), absolute)

    tokens = asyncio.run(
        service.rotate(
            RotationAttempt(
                SecretText("synthetic-refresh-value-for-rotation"),
                SecretText("synthetic-csrf-value-for-rotation"),
                uuid4(),
                now,
            )
        )
    )

    assert tokens is not None
    assert tokens.absolute_expires_at == absolute
    assert tokens.refresh_expires_at == absolute
    assert tokens.access_expires_at == now + ACCESS_LIFETIME


def test_rotation_limit_uses_stable_server_side_family() -> None:
    repository = CapturingSessionRepository()
    passwords = Argon2idPasswordService()
    credentials = _credentials()
    service = SessionService(
        repository,
        credentials,
        passwords,
        passwords.hash(SecretText("synthetic-dummy-password")),
        DevelopmentSubjectAbuseControl(limit=1, window=timedelta(minutes=5)),
    )
    now = datetime(2026, 8, 29, tzinfo=UTC)
    repository.rotation_lease = RotationLease(uuid4(), uuid4(), uuid4(), now + timedelta(days=1))

    first = asyncio.run(
        service.rotate(
            RotationAttempt(
                SecretText("synthetic-first-refresh-value-for-rotation"),
                SecretText("synthetic-first-csrf-value-for-rotation"),
                uuid4(),
                now,
            )
        )
    )
    assert first is not None

    with pytest.raises(RefreshRateLimited) as blocked:
        asyncio.run(
            service.rotate(
                RotationAttempt(
                    SecretText("synthetic-second-refresh-value-for-rotation"),
                    SecretText("synthetic-second-csrf-value-for-rotation"),
                    uuid4(),
                    now,
                )
            )
        )
    assert blocked.value.retry_after == timedelta(minutes=5)
