"""Framework-free password-change and recovery orchestration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.account_security import (
    AccountSecurityService,
    DevelopmentRecoveryOutbox,
    PasswordChangeAttempt,
    PasswordChangeCandidate,
    RecoveryConfirmation,
    RecoveryRequest,
)
from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialService,
    PasswordDigest,
    SecretBytes,
    SecretText,
)


class FakeRepository:
    def __init__(self, passwords: Argon2idPasswordService) -> None:
        self.account_id = uuid4()
        self.session_id = uuid4()
        self.current = passwords.hash(SecretText("synthetic-current-password"))
        self.changed: PasswordDigest | None = None
        self.denied = 0
        self.recipient: str | None = None
        self.confirmed: PasswordDigest | None = None

    async def password_change_candidate(
        self, account_id: object, current_session_id: object
    ) -> PasswordChangeCandidate | None:
        if account_id == self.account_id and current_session_id == self.session_id:
            return PasswordChangeCandidate(self.account_id, self.current)
        return None

    async def password_change_denied(self, account_id: object, correlation_id: object) -> None:
        del account_id, correlation_id
        self.denied += 1

    async def change_password(self, attempt: object, password_digest: PasswordDigest) -> bool:
        del attempt
        self.changed = password_digest
        return True

    async def issue_recovery(
        self, normalized_email: str | None, credential: object, correlation_id: object
    ) -> str | None:
        del credential, correlation_id
        return self.recipient if normalized_email == self.recipient else None

    async def confirm_recovery(self, confirmation: object, password_digest: PasswordDigest) -> bool:
        del confirmation
        self.confirmed = password_digest
        return True


def _service() -> tuple[
    AccountSecurityService,
    FakeRepository,
    DevelopmentRecoveryOutbox,
    Argon2idPasswordService,
]:
    passwords = Argon2idPasswordService()
    repository = FakeRepository(passwords)
    outbox = DevelopmentRecoveryOutbox()
    credentials = OpaqueCredentialService(
        KeyedDigestService(SecretBytes(b"synthetic-account-security-key-material"))
    )
    return (
        AccountSecurityService(repository, credentials, passwords, outbox),
        repository,
        outbox,
        passwords,
    )


def test_password_change_requires_current_password_and_hashes_replacement() -> None:
    async def exercise() -> None:
        service, repository, _, passwords = _service()
        denied = await service.change_password(
            PasswordChangeAttempt(
                account_id=repository.account_id,
                current_session_id=repository.session_id,
                current_password=SecretText("synthetic-wrong-password"),
                new_password=SecretText("synthetic-replacement-password"),
                correlation_id=uuid4(),
                now=datetime(2026, 8, 9, tzinfo=UTC),
            )
        )
        changed = await service.change_password(
            PasswordChangeAttempt(
                account_id=repository.account_id,
                current_session_id=repository.session_id,
                current_password=SecretText("synthetic-current-password"),
                new_password=SecretText("synthetic-replacement-password"),
                correlation_id=uuid4(),
                now=datetime(2026, 8, 9, tzinfo=UTC),
            )
        )
        assert denied is False
        assert changed is True
        assert repository.denied == 1
        assert repository.changed is not None
        assert passwords.verify(
            SecretText("synthetic-replacement-password"), repository.changed
        ).matches
        assert "replacement-password" not in repr(repository.changed)

    asyncio.run(exercise())


def test_recovery_request_is_concealed_and_confirmation_hashes_password() -> None:
    async def exercise() -> None:
        service, repository, outbox, passwords = _service()
        now = datetime(2026, 8, 9, tzinfo=UTC)
        repository.recipient = "member@example.invalid"
        await service.request_recovery(RecoveryRequest("MEMBER@example.invalid", uuid4(), now))
        delivery = outbox.drain()
        assert len(delivery) == 1
        assert delivery[0].recipient == "member@example.invalid"
        assert "SecretText" in repr(delivery[0].value)

        await service.request_recovery(RecoveryRequest("missing@example.invalid", uuid4(), now))
        assert outbox.drain() == ()

        completed = await service.confirm_recovery(
            RecoveryConfirmation(
                delivery[0].value,
                SecretText("synthetic-recovered-password"),
                uuid4(),
                now,
            )
        )
        assert completed is True
        assert repository.confirmed is not None
        assert passwords.verify(
            SecretText("synthetic-recovered-password"), repository.confirmed
        ).matches

    asyncio.run(exercise())
