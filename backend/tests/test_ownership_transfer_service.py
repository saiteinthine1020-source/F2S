"""Framework-free ownership-transfer orchestration and notification tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialService,
    SecretBytes,
    SecretText,
)
from app.modules.ownership_transfer import (
    CancelOwnershipTransfer,
    ConfirmOwnershipTransfer,
    DevelopmentOwnershipOutbox,
    InitiateOwnershipTransfer,
    InitiationCandidate,
    OwnershipNotificationKind,
    OwnershipReauthenticationFailed,
    OwnershipTransferCompleted,
    OwnershipTransferInitiated,
    OwnershipTransferReference,
    OwnershipTransferService,
    OwnershipTransferStatus,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole


class FakeRepository:
    def __init__(self, passwords: Argon2idPasswordService) -> None:
        self.current = passwords.hash(SecretText("synthetic-current-password"))
        self.issued: object | None = None
        self.denied = 0
        self.cancelled: CancelOwnershipTransfer | None = None
        self.transfer = OwnershipTransferReference(
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            WorkspaceRole.CONTRIBUTOR,
            OwnershipTransferStatus.INITIATED,
            datetime(2026, 8, 10, tzinfo=UTC),
            1,
        )

    async def initiation_candidate(
        self, command: InitiateOwnershipTransfer
    ) -> InitiationCandidate | None:
        del command
        return InitiationCandidate(self.current)

    async def initiation_denied(self, command: InitiateOwnershipTransfer) -> None:
        del command
        self.denied += 1

    async def initiate(
        self, command: InitiateOwnershipTransfer, credential: object
    ) -> OwnershipTransferInitiated:
        del command
        self.issued = credential
        return OwnershipTransferInitiated(self.transfer, "target@example.invalid")

    async def confirm(self, command: ConfirmOwnershipTransfer) -> OwnershipTransferCompleted:
        del command
        completed = OwnershipTransferReference(
            self.transfer.id,
            self.transfer.workspace_id,
            self.transfer.current_owner_membership_id,
            self.transfer.target_membership_id,
            self.transfer.former_owner_role,
            OwnershipTransferStatus.COMPLETED,
            self.transfer.expires_at,
            3,
        )
        return OwnershipTransferCompleted(
            completed, "former@example.invalid", "target@example.invalid"
        )

    async def cancel(self, command: CancelOwnershipTransfer) -> None:
        self.cancelled = command


def _context(workspace_id: UUID, membership_id: UUID) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), workspace_id, membership_id, WorkspaceRole.ADMIN, uuid4())


def _service() -> tuple[OwnershipTransferService, FakeRepository, DevelopmentOwnershipOutbox]:
    passwords = Argon2idPasswordService()
    repository = FakeRepository(passwords)
    outbox = DevelopmentOwnershipOutbox()
    credentials = OpaqueCredentialService(
        KeyedDigestService(SecretBytes(b"synthetic-ownership-transfer-key-material"))
    )
    return (
        OwnershipTransferService(repository, credentials, passwords, outbox),
        repository,
        outbox,
    )


def test_initiation_reauthenticates_issues_digest_credential_and_notifies_target() -> None:
    async def exercise() -> None:
        service, repository, outbox = _service()
        transfer = repository.transfer
        command = InitiateOwnershipTransfer(
            _context(transfer.workspace_id, transfer.current_owner_membership_id),
            uuid4(),
            transfer.target_membership_id,
            WorkspaceRole.CONTRIBUTOR,
            SecretText("synthetic-current-password"),
            datetime(2026, 8, 9, tzinfo=UTC),
        )
        result = await service.initiate(command)
        assert result == transfer
        assert repository.issued is not None
        batch = outbox.drain()
        assert len(batch) == 1 and len(batch[0]) == 1
        intent = batch[0][0]
        assert intent.kind is OwnershipNotificationKind.CONFIRMATION_REQUIRED
        assert intent.recipient == "target@example.invalid"
        assert intent.value is not None
        assert intent.expires_at == command.now + timedelta(minutes=30)
        assert intent.value.reveal() not in repr(intent)

    asyncio.run(exercise())


def test_wrong_owner_password_creates_no_transfer_or_notification() -> None:
    async def exercise() -> None:
        service, repository, outbox = _service()
        transfer = repository.transfer
        with pytest.raises(OwnershipReauthenticationFailed):
            await service.initiate(
                InitiateOwnershipTransfer(
                    _context(transfer.workspace_id, transfer.current_owner_membership_id),
                    uuid4(),
                    transfer.target_membership_id,
                    WorkspaceRole.ADVISOR,
                    SecretText("synthetic-wrong-password"),
                    datetime(2026, 8, 9, tzinfo=UTC),
                )
            )
        assert repository.issued is None
        assert repository.denied == 1
        assert outbox.drain() == ()

    asyncio.run(exercise())


def test_completion_batches_notifications_for_both_parties_and_cancel_is_versioned() -> None:
    async def exercise() -> None:
        service, repository, outbox = _service()
        transfer = repository.transfer
        completed = await service.confirm(
            ConfirmOwnershipTransfer(
                _context(transfer.workspace_id, transfer.target_membership_id),
                transfer.id,
                SecretText("synthetic-confirmation-value"),
                datetime(2026, 8, 9, tzinfo=UTC),
            )
        )
        assert completed.status is OwnershipTransferStatus.COMPLETED
        batch = outbox.drain()
        assert {intent.recipient for intent in batch[0]} == {
            "former@example.invalid",
            "target@example.invalid",
        }
        assert all(
            intent.kind is OwnershipNotificationKind.TRANSFER_COMPLETED for intent in batch[0]
        )
        cancel = CancelOwnershipTransfer(
            _context(transfer.workspace_id, transfer.current_owner_membership_id),
            transfer.id,
            1,
            datetime(2026, 8, 9, tzinfo=UTC),
        )
        await service.cancel(cancel)
        assert repository.cancelled == cancel

    asyncio.run(exercise())
