"""Framework-free password change and concealed account-recovery orchestration."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity_security import (
    DEFAULT_CHALLENGE_LIFETIME,
    Argon2idPasswordService,
    IssuedOpaqueCredential,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretText,
    normalize_email,
)


@dataclass(frozen=True, slots=True)
class PasswordChangeCandidate:
    account_id: UUID
    password_digest: PasswordDigest


@dataclass(frozen=True, slots=True)
class PasswordChangeAttempt:
    account_id: UUID
    current_session_id: UUID
    current_password: SecretText
    new_password: SecretText
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class RecoveryRequest:
    email: str
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class RecoveryConfirmation:
    value: SecretText
    new_password: SecretText
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class RecoveryDelivery:
    recipient: str
    value: SecretText
    expires_at: datetime


class RecoveryDeliveryUnavailable(Exception):
    """The production recovery delivery boundary is not configured."""


class RecoveryDeliveryPort(Protocol):
    async def deliver(self, delivery: RecoveryDelivery | None) -> None: ...


class AccountSecurityRepository(Protocol):
    async def password_change_candidate(
        self, account_id: UUID, current_session_id: UUID
    ) -> PasswordChangeCandidate | None: ...

    async def change_password(
        self, attempt: PasswordChangeAttempt, password_digest: PasswordDigest
    ) -> bool: ...

    async def password_change_denied(self, account_id: UUID, correlation_id: UUID) -> None: ...

    async def issue_recovery(
        self,
        normalized_email: str | None,
        credential: IssuedOpaqueCredential,
        correlation_id: UUID,
    ) -> str | None: ...

    async def confirm_recovery(
        self, confirmation: RecoveryConfirmation, password_digest: PasswordDigest
    ) -> bool: ...


class DevelopmentRecoveryOutbox(RecoveryDeliveryPort):
    """Process-local development delivery that never captures concealed misses."""

    def __init__(self) -> None:
        self._deliveries: list[RecoveryDelivery] = []

    async def deliver(self, delivery: RecoveryDelivery | None) -> None:
        if delivery is not None:
            self._deliveries.append(delivery)

    def drain(self) -> tuple[RecoveryDelivery, ...]:
        deliveries = tuple(self._deliveries)
        self._deliveries.clear()
        return deliveries


class RejectingRecoveryDelivery(RecoveryDeliveryPort):
    """Uniformly fail closed until production has a durable delivery adapter."""

    async def deliver(self, delivery: RecoveryDelivery | None) -> None:
        del delivery
        raise RecoveryDeliveryUnavailable


class AccountSecurityService:
    def __init__(
        self,
        repository: AccountSecurityRepository,
        credentials: OpaqueCredentialService,
        passwords: Argon2idPasswordService,
        delivery: RecoveryDeliveryPort,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._passwords = passwords
        self._delivery = delivery

    async def change_password(self, attempt: PasswordChangeAttempt) -> bool:
        candidate = await self._repository.password_change_candidate(
            attempt.account_id, attempt.current_session_id
        )
        if (
            candidate is None
            or not self._passwords.verify(
                attempt.current_password, candidate.password_digest
            ).matches
        ):
            await self._repository.password_change_denied(
                attempt.account_id, attempt.correlation_id
            )
            return False
        digest = self._passwords.hash(attempt.new_password)
        return await self._repository.change_password(attempt, digest)

    async def request_recovery(self, request: RecoveryRequest) -> None:
        try:
            normalized_email: str | None = normalize_email(request.email)
        except ValueError:
            normalized_email = None
        credential = self._credentials.issue(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            now=request.now,
            lifetime=DEFAULT_CHALLENGE_LIFETIME,
        )
        recipient = await self._repository.issue_recovery(
            normalized_email, credential, request.correlation_id
        )
        delivery = (
            RecoveryDelivery(recipient, credential.value, credential.record.expires_at)
            if recipient is not None
            else None
        )
        await self._delivery.deliver(delivery)

    async def confirm_recovery(self, confirmation: RecoveryConfirmation) -> bool:
        digest = self._passwords.hash(confirmation.new_password)
        return await self._repository.confirm_recovery(confirmation, digest)


def recovery_now() -> datetime:
    return datetime.now(UTC)
