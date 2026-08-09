"""Framework-free high-assurance workspace ownership-transfer orchestration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.modules.identity_security import (
    Argon2idPasswordService,
    IssuedOpaqueCredential,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretText,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

OWNERSHIP_TRANSFER_LIFETIME = timedelta(minutes=30)


class OwnershipTransferStatus(StrEnum):
    INITIATED = "INITIATED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class OwnershipReauthenticationFailed(Exception):
    """The owner did not prove the current account credential."""


class OwnershipTransferConfirmationDenied(Exception):
    """The target proof was invalid, expired, foreign, or already consumed."""


class OwnershipTransferStateConflict(Exception):
    """The requested transition is not valid from the persisted state."""


class OwnershipTransferVersionMismatch(Exception):
    """The supplied transfer version is stale."""


class OwnershipNotificationUnavailable(Exception):
    """The required ownership notification boundary is unavailable."""


@dataclass(frozen=True, slots=True)
class InitiationCandidate:
    password_digest: PasswordDigest


@dataclass(frozen=True, slots=True)
class InitiateOwnershipTransfer:
    context: AuthorizationContext
    current_session_id: UUID
    target_membership_id: UUID
    former_owner_role: WorkspaceRole
    current_password: SecretText
    now: datetime


@dataclass(frozen=True, slots=True)
class ConfirmOwnershipTransfer:
    context: AuthorizationContext
    transfer_id: UUID
    value: SecretText
    now: datetime


@dataclass(frozen=True, slots=True)
class CancelOwnershipTransfer:
    context: AuthorizationContext
    transfer_id: UUID
    expected_version: int
    now: datetime


@dataclass(frozen=True, slots=True)
class OwnershipTransferReference:
    id: UUID
    workspace_id: UUID
    current_owner_membership_id: UUID
    target_membership_id: UUID
    former_owner_role: WorkspaceRole
    status: OwnershipTransferStatus
    expires_at: datetime
    version: int


class OwnershipNotificationKind(StrEnum):
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    TRANSFER_COMPLETED = "TRANSFER_COMPLETED"


@dataclass(frozen=True, slots=True)
class OwnershipNotificationIntent:
    recipient: str
    kind: OwnershipNotificationKind
    transfer_id: UUID
    value: SecretText | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OwnershipTransferInitiated:
    transfer: OwnershipTransferReference
    target_recipient: str


@dataclass(frozen=True, slots=True)
class OwnershipTransferCompleted:
    transfer: OwnershipTransferReference
    former_owner_recipient: str
    new_owner_recipient: str


class OwnershipTransferRepository(Protocol):
    async def initiation_candidate(
        self, command: InitiateOwnershipTransfer
    ) -> InitiationCandidate | None: ...

    async def initiation_denied(self, command: InitiateOwnershipTransfer) -> None: ...

    async def initiate(
        self, command: InitiateOwnershipTransfer, credential: IssuedOpaqueCredential
    ) -> OwnershipTransferInitiated: ...

    async def confirm(self, command: ConfirmOwnershipTransfer) -> OwnershipTransferCompleted: ...

    async def cancel(self, command: CancelOwnershipTransfer) -> None: ...


class OwnershipNotificationPort(Protocol):
    async def deliver(self, intents: tuple[OwnershipNotificationIntent, ...]) -> None: ...


class DevelopmentOwnershipOutbox(OwnershipNotificationPort):
    """Process-local development capture for one atomic notification batch."""

    def __init__(self) -> None:
        self._batches: list[tuple[OwnershipNotificationIntent, ...]] = []

    async def deliver(self, intents: tuple[OwnershipNotificationIntent, ...]) -> None:
        self._batches.append(intents)

    def drain(self) -> tuple[tuple[OwnershipNotificationIntent, ...], ...]:
        batches = tuple(self._batches)
        self._batches.clear()
        return batches


class RejectingOwnershipNotifications(OwnershipNotificationPort):
    """Fail closed until production supplies a durable batch notification adapter."""

    async def deliver(self, intents: tuple[OwnershipNotificationIntent, ...]) -> None:
        del intents
        raise OwnershipNotificationUnavailable


class OwnershipTransferService:
    def __init__(
        self,
        repository: OwnershipTransferRepository,
        credentials: OpaqueCredentialService,
        passwords: Argon2idPasswordService,
        notifications: OwnershipNotificationPort,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._passwords = passwords
        self._notifications = notifications

    async def initiate(self, command: InitiateOwnershipTransfer) -> OwnershipTransferReference:
        if command.former_owner_role not in {
            WorkspaceRole.CONTRIBUTOR,
            WorkspaceRole.ADVISOR,
        }:
            raise OwnershipTransferStateConflict
        candidate = await self._repository.initiation_candidate(command)
        if (
            candidate is None
            or not self._passwords.verify(
                command.current_password, candidate.password_digest
            ).matches
        ):
            await self._repository.initiation_denied(command)
            raise OwnershipReauthenticationFailed
        credential = self._credentials.issue(
            OpaqueCredentialPurpose.OWNERSHIP_TRANSFER,
            now=command.now,
            lifetime=OWNERSHIP_TRANSFER_LIFETIME,
        )
        initiated = await self._repository.initiate(command, credential)
        await self._notifications.deliver(
            (
                OwnershipNotificationIntent(
                    recipient=initiated.target_recipient,
                    kind=OwnershipNotificationKind.CONFIRMATION_REQUIRED,
                    transfer_id=initiated.transfer.id,
                    value=credential.value,
                    expires_at=credential.record.expires_at,
                ),
            )
        )
        return initiated.transfer

    async def confirm(self, command: ConfirmOwnershipTransfer) -> OwnershipTransferReference:
        completed = await self._repository.confirm(command)
        await self._notifications.deliver(
            (
                OwnershipNotificationIntent(
                    recipient=completed.former_owner_recipient,
                    kind=OwnershipNotificationKind.TRANSFER_COMPLETED,
                    transfer_id=completed.transfer.id,
                ),
                OwnershipNotificationIntent(
                    recipient=completed.new_owner_recipient,
                    kind=OwnershipNotificationKind.TRANSFER_COMPLETED,
                    transfer_id=completed.transfer.id,
                ),
            )
        )
        return completed.transfer

    async def cancel(self, command: CancelOwnershipTransfer) -> None:
        if command.expected_version <= 0:
            raise OwnershipTransferVersionMismatch
        await self._repository.cancel(command)
