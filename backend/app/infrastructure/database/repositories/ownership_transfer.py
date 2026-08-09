"""PostgreSQL adapter for atomic, target-confirmed workspace ownership transfer."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import AuthSession
from app.infrastructure.database.models.workspace_access import (
    OwnershipTransfer,
    Workspace,
    WorkspaceMembership,
)
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.identity_security import (
    CredentialVerification,
    IssuedOpaqueCredential,
    KeyedDigest,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    StoredOpaqueCredential,
)
from app.modules.ownership_transfer import (
    CancelOwnershipTransfer,
    ConfirmOwnershipTransfer,
    InitiateOwnershipTransfer,
    InitiationCandidate,
    OwnershipTransferCompleted,
    OwnershipTransferConfirmationDenied,
    OwnershipTransferInitiated,
    OwnershipTransferReference,
    OwnershipTransferRepository,
    OwnershipTransferStateConflict,
    OwnershipTransferStatus,
    OwnershipTransferVersionMismatch,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceRole,
)


class SqlAlchemyOwnershipTransferRepository(OwnershipTransferRepository):
    def __init__(self, session: AsyncSession, credentials: OpaqueCredentialService) -> None:
        self._session = session
        self._credentials = credentials

    async def initiation_candidate(
        self, command: InitiateOwnershipTransfer
    ) -> InitiationCandidate | None:
        row = (
            await self._session.execute(
                select(UserAccount, Workspace, WorkspaceMembership)
                .join(
                    WorkspaceMembership,
                    WorkspaceMembership.user_account_id == UserAccount.id,
                )
                .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
                .join(AuthSession, AuthSession.user_account_id == UserAccount.id)
                .where(
                    UserAccount.id == command.context.actor_account_id,
                    UserAccount.status == "ACTIVE",
                    AuthSession.id == command.current_session_id,
                    AuthSession.status == "ACTIVE",
                    Workspace.id == command.context.workspace_id,
                    Workspace.status == "ACTIVE",
                    Workspace.owner_membership_id == command.context.membership_id,
                    WorkspaceMembership.id == command.context.membership_id,
                    WorkspaceMembership.workspace_id == command.context.workspace_id,
                    WorkspaceMembership.user_account_id == command.context.actor_account_id,
                    WorkspaceMembership.role == "ADMIN",
                    WorkspaceMembership.status == "ACTIVE",
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None or row[0].password_digest is None:
            return None
        return InitiationCandidate(PasswordDigest(row[0].password_digest))

    async def initiation_denied(self, command: InitiateOwnershipTransfer) -> None:
        await self._audit(
            command.context,
            AuditAction.OWNERSHIP_TRANSFER_INITIATED,
            AuditResult.DENIED,
            reason=AuditReason.INVALID_CREDENTIALS,
        )

    async def initiate(
        self, command: InitiateOwnershipTransfer, credential: IssuedOpaqueCredential
    ) -> OwnershipTransferInitiated:
        workspace = await self._lock_workspace(command.context.workspace_id)
        if workspace.owner_membership_id != command.context.membership_id:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        rows = (
            await self._session.execute(
                select(WorkspaceMembership, UserAccount)
                .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
                .where(
                    WorkspaceMembership.workspace_id == command.context.workspace_id,
                    WorkspaceMembership.id.in_(
                        (command.context.membership_id, command.target_membership_id)
                    ),
                )
                .order_by(WorkspaceMembership.id)
                .with_for_update()
            )
        ).all()
        members = {membership.id: (membership, account) for membership, account in rows}
        owner_pair = members.get(command.context.membership_id)
        target_pair = members.get(command.target_membership_id)
        if owner_pair is None or target_pair is None:
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_INITIATED,
                AuditResult.DENIED,
                reason=AuditReason.RESOURCE_NOT_FOUND,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        owner, owner_account = owner_pair
        target, target_account = target_pair
        if (
            owner.user_account_id != command.context.actor_account_id
            or owner.role != "ADMIN"
            or owner.status != "ACTIVE"
            or owner_account.status != "ACTIVE"
        ):
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if (
            target.id == owner.id
            or target.role not in {"CONTRIBUTOR", "ADVISOR"}
            or target.status != "ACTIVE"
            or target_account.status != "ACTIVE"
        ):
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_INITIATED,
                AuditResult.DENIED,
                reason=AuditReason.MEMBERSHIP_INACTIVE,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)

        await self._expire_due(command.context, command.now)
        await self._cancel_open(command.context, command.now)
        transfer = OwnershipTransfer(
            id=uuid4(),
            workspace_id=workspace.id,
            current_owner_membership_id=owner.id,
            target_membership_id=target.id,
            target_confirmation_digest=credential.record.digest.for_persistence(),
            digest_algorithm_code="SHA256",
            former_owner_role_code=command.former_owner_role.value,
            status="INITIATED",
            initiated_at=credential.record.issued_at,
            expires_at=credential.record.expires_at,
        )
        self._session.add(transfer)
        await self._session.flush()
        await self._audit(
            command.context,
            AuditAction.OWNERSHIP_TRANSFER_INITIATED,
            AuditResult.SUCCEEDED,
            transfer_id=transfer.id,
        )
        return OwnershipTransferInitiated(
            self._reference(transfer), target_account.normalized_email
        )

    async def confirm(self, command: ConfirmOwnershipTransfer) -> OwnershipTransferCompleted:
        workspace = await self._lock_workspace(command.context.workspace_id)
        transfer = await self._session.scalar(
            select(OwnershipTransfer)
            .where(
                OwnershipTransfer.id == command.transfer_id,
                OwnershipTransfer.workspace_id == command.context.workspace_id,
            )
            .with_for_update()
        )
        if transfer is None:
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_CONFIRMED,
                AuditResult.DENIED,
                reason=AuditReason.INVALID_CREDENTIALS,
            )
            raise OwnershipTransferConfirmationDenied
        if transfer.status == "INITIATED" and command.now >= transfer.expires_at:
            transfer.status = "EXPIRED"
            transfer.expired_at = command.now
            transfer.version += 1
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_EXPIRED,
                AuditResult.SUCCEEDED,
                transfer_id=transfer.id,
            )
            raise OwnershipTransferConfirmationDenied
        verification = self._credentials.verify(
            OpaqueCredentialPurpose.OWNERSHIP_TRANSFER,
            command.value,
            self._stored(transfer),
            now=command.now,
        )
        if transfer.status != "INITIATED" or verification is not CredentialVerification.VALID:
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_CONFIRMED,
                AuditResult.DENIED,
                reason=self._verification_reason(verification),
            )
            raise OwnershipTransferConfirmationDenied
        if (
            transfer.target_membership_id != command.context.membership_id
            or workspace.owner_membership_id != transfer.current_owner_membership_id
        ):
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_CONFIRMED,
                AuditResult.DENIED,
                reason=AuditReason.PERMISSION_DENIED,
            )
            raise OwnershipTransferConfirmationDenied

        rows = (
            await self._session.execute(
                select(WorkspaceMembership, UserAccount)
                .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
                .where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.id.in_(
                        (
                            transfer.current_owner_membership_id,
                            transfer.target_membership_id,
                        )
                    ),
                )
                .order_by(WorkspaceMembership.id)
                .with_for_update()
            )
        ).all()
        members = {membership.id: (membership, account) for membership, account in rows}
        owner_pair = members.get(transfer.current_owner_membership_id)
        target_pair = members.get(transfer.target_membership_id)
        if owner_pair is None or target_pair is None:
            raise OwnershipTransferConfirmationDenied
        owner, owner_account = owner_pair
        target, target_account = target_pair
        if (
            owner.role != "ADMIN"
            or owner.status != "ACTIVE"
            or owner_account.status != "ACTIVE"
            or target.role not in {"CONTRIBUTOR", "ADVISOR"}
            or target.status != "ACTIVE"
            or target_account.status != "ACTIVE"
            or target.user_account_id != command.context.actor_account_id
            or target.role != command.context.role.value
        ):
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_CONFIRMED,
                AuditResult.DENIED,
                reason=AuditReason.OWNERSHIP_INVARIANT,
            )
            raise OwnershipTransferConfirmationDenied

        transfer.status = "CONFIRMED"
        transfer.confirmed_at = command.now
        transfer.version += 1
        await self._audit(
            command.context,
            AuditAction.OWNERSHIP_TRANSFER_CONFIRMED,
            AuditResult.SUCCEEDED,
            transfer_id=transfer.id,
        )

        # Demote before promotion to satisfy the immediate one-Active-Admin index. The
        # deferred owner FK permits the invariant to be restored before transaction commit.
        owner.role = transfer.former_owner_role_code
        owner.version += 1
        await self._session.flush()
        target.role = "ADMIN"
        target.version += 1
        await self._session.flush()
        workspace.owner_membership_id = target.id
        workspace.version += 1
        transfer.status = "COMPLETED"
        transfer.completed_at = command.now
        transfer.version += 1
        await self._revoke_sessions(owner_account.id, command.now)
        await self._revoke_sessions(target_account.id, command.now)
        await self._session.flush()
        await self._audit(
            command.context,
            AuditAction.OWNERSHIP_TRANSFER_COMPLETED,
            AuditResult.SUCCEEDED,
            transfer_id=transfer.id,
        )
        await self._audit(
            command.context,
            AuditAction.SESSION_REVOKED,
            AuditResult.SUCCEEDED,
            resource_type=AuditResourceType.SESSION,
        )
        return OwnershipTransferCompleted(
            self._reference(transfer),
            owner_account.normalized_email,
            target_account.normalized_email,
        )

    async def cancel(self, command: CancelOwnershipTransfer) -> None:
        workspace = await self._lock_workspace(command.context.workspace_id)
        if workspace.owner_membership_id != command.context.membership_id:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        owner = await self._session.scalar(
            select(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .where(
                WorkspaceMembership.id == command.context.membership_id,
                WorkspaceMembership.workspace_id == command.context.workspace_id,
                WorkspaceMembership.user_account_id == command.context.actor_account_id,
                WorkspaceMembership.role == "ADMIN",
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.status == "ACTIVE",
            )
            .with_for_update()
        )
        if owner is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        transfer = await self._session.scalar(
            select(OwnershipTransfer)
            .where(
                OwnershipTransfer.id == command.transfer_id,
                OwnershipTransfer.workspace_id == command.context.workspace_id,
                OwnershipTransfer.current_owner_membership_id == command.context.membership_id,
            )
            .with_for_update()
        )
        if transfer is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if transfer.version != command.expected_version:
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_CANCELLED,
                AuditResult.DENIED,
                reason=AuditReason.STALE_VERSION,
            )
            raise OwnershipTransferVersionMismatch
        if transfer.status == "INITIATED" and command.now >= transfer.expires_at:
            transfer.status = "EXPIRED"
            transfer.expired_at = command.now
            transfer.version += 1
            await self._audit(
                command.context,
                AuditAction.OWNERSHIP_TRANSFER_EXPIRED,
                AuditResult.SUCCEEDED,
                transfer_id=transfer.id,
            )
            raise OwnershipTransferStateConflict
        if transfer.status != "INITIATED":
            raise OwnershipTransferStateConflict
        transfer.status = "CANCELLED"
        transfer.cancelled_at = command.now
        transfer.reason_code = "OWNER_CANCELLED"
        transfer.version += 1
        await self._audit(
            command.context,
            AuditAction.OWNERSHIP_TRANSFER_CANCELLED,
            AuditResult.SUCCEEDED,
            transfer_id=transfer.id,
        )

    async def _lock_workspace(self, workspace_id: UUID) -> Workspace:
        workspace = await self._session.scalar(
            select(Workspace)
            .where(Workspace.id == workspace_id, Workspace.status == "ACTIVE")
            .with_for_update()
        )
        if workspace is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return workspace

    async def _expire_due(self, context: AuthorizationContext, now: datetime) -> None:
        expired_ids = (
            await self._session.scalars(
                update(OwnershipTransfer)
                .where(
                    OwnershipTransfer.workspace_id == context.workspace_id,
                    OwnershipTransfer.status == "INITIATED",
                    OwnershipTransfer.expires_at <= now,
                )
                .values(
                    status="EXPIRED",
                    expired_at=now,
                    version=OwnershipTransfer.version + 1,
                )
                .returning(OwnershipTransfer.id)
            )
        ).all()
        for transfer_id in expired_ids:
            await self._audit(
                context,
                AuditAction.OWNERSHIP_TRANSFER_EXPIRED,
                AuditResult.SUCCEEDED,
                transfer_id=transfer_id,
            )

    async def _cancel_open(self, context: AuthorizationContext, now: datetime) -> None:
        cancelled_ids = (
            await self._session.scalars(
                update(OwnershipTransfer)
                .where(
                    OwnershipTransfer.workspace_id == context.workspace_id,
                    OwnershipTransfer.status == "INITIATED",
                )
                .values(
                    status="CANCELLED",
                    cancelled_at=now,
                    reason_code="SUPERSEDED",
                    version=OwnershipTransfer.version + 1,
                )
                .returning(OwnershipTransfer.id)
            )
        ).all()
        for transfer_id in cancelled_ids:
            await self._audit(
                context,
                AuditAction.OWNERSHIP_TRANSFER_CANCELLED,
                AuditResult.SUCCEEDED,
                transfer_id=transfer_id,
            )

    async def _revoke_sessions(self, account_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.user_account_id == account_id, AuthSession.status == "ACTIVE")
            .values(
                status="REVOKED",
                revoked_at=now,
                revoke_reason_code="OWNERSHIP_TRANSFER",
                version=AuthSession.version + 1,
            )
        )

    def _stored(self, transfer: OwnershipTransfer) -> StoredOpaqueCredential:
        return StoredOpaqueCredential(
            purpose=OpaqueCredentialPurpose.OWNERSHIP_TRANSFER,
            digest=KeyedDigest(transfer.target_confirmation_digest),
            issued_at=transfer.initiated_at,
            expires_at=transfer.expires_at,
            consumed_at=transfer.confirmed_at,
            revoked_at=transfer.cancelled_at,
        )

    @staticmethod
    def _reference(transfer: OwnershipTransfer) -> OwnershipTransferReference:
        return OwnershipTransferReference(
            id=transfer.id,
            workspace_id=transfer.workspace_id,
            current_owner_membership_id=transfer.current_owner_membership_id,
            target_membership_id=transfer.target_membership_id,
            former_owner_role=WorkspaceRole(transfer.former_owner_role_code),
            status=OwnershipTransferStatus(transfer.status),
            expires_at=transfer.expires_at,
            version=transfer.version,
        )

    async def _audit(
        self,
        context: AuthorizationContext,
        action: AuditAction,
        result: AuditResult,
        *,
        transfer_id: UUID | None = None,
        reason: AuditReason | None = None,
        resource_type: AuditResourceType = AuditResourceType.OWNERSHIP_TRANSFER,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=action,
                module=AuditModule.WORKSPACE_ACCESS,
                result=result,
                correlation_id=context.correlation_id,
                resource_type=resource_type,
                resource_id=transfer_id if result is AuditResult.SUCCEEDED else None,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.OWNERSHIP_TRANSFER,
            )
        )

    @staticmethod
    def _verification_reason(verification: CredentialVerification) -> AuditReason:
        return {
            CredentialVerification.EXPIRED: AuditReason.EXPIRED,
            CredentialVerification.CONSUMED: AuditReason.REPLAY_DETECTED,
            CredentialVerification.REVOKED: AuditReason.REVOKED,
        }.get(verification, AuditReason.INVALID_CREDENTIALS)
