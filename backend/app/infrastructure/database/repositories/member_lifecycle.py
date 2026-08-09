"""Workspace-scoped PostgreSQL membership lifecycle adapter."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import ActivationChallenge, AuthSession
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
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
from app.modules.member_lifecycle import (
    InvalidMembershipTransition,
    MemberLifecycleRepository,
    MemberReference,
    MembershipMutation,
    MembershipOperation,
    MembershipStatus,
    MemberVersionMismatch,
    OwnershipInvariantViolation,
    validate_transition,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)


class SqlAlchemyMemberLifecycleRepository(MemberLifecycleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_members(self, context: AuthorizationContext) -> tuple[MemberReference, ...]:
        await self._require_admin(context)
        statement = (
            select(
                WorkspaceMembership.id,
                UserAccount.normalized_email,
                UserAccount.display_name,
                WorkspaceMembership.role,
                WorkspaceMembership.status,
                UserAccount.status.label("account_status"),
                UserAccount.preferred_language,
                UserAccount.timezone,
                func.max(AuthSession.issued_at).label("last_login_at"),
                WorkspaceMembership.created_at,
                WorkspaceMembership.version,
            )
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .outerjoin(AuthSession, AuthSession.user_account_id == UserAccount.id)
            .where(WorkspaceMembership.workspace_id == context.workspace_id)
            .group_by(
                WorkspaceMembership.id,
                UserAccount.id,
                UserAccount.normalized_email,
                UserAccount.display_name,
                WorkspaceMembership.role,
                WorkspaceMembership.status,
                UserAccount.status,
                UserAccount.preferred_language,
                UserAccount.timezone,
                WorkspaceMembership.created_at,
                WorkspaceMembership.version,
            )
            .order_by(UserAccount.display_name, WorkspaceMembership.id)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(self._from_row(row) for row in rows)

    async def mutate(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        mutation: MembershipMutation,
        now: datetime,
    ) -> MemberReference:
        await self._require_admin(context)
        workspace = await self._session.scalar(
            select(Workspace)
            .where(Workspace.id == context.workspace_id, Workspace.status == "ACTIVE")
            .with_for_update()
        )
        if workspace is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        row = (
            await self._session.execute(
                select(WorkspaceMembership, UserAccount)
                .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
                .where(
                    WorkspaceMembership.workspace_id == context.workspace_id,
                    WorkspaceMembership.id == membership_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        membership, account = row
        action = self._action(mutation.operation)
        if membership.id == workspace.owner_membership_id or membership.role == "ADMIN":
            await self._audit_denied(context, action, AuditReason.OWNERSHIP_INVARIANT)
            raise OwnershipInvariantViolation
        if membership.version != expected_version:
            await self._audit_denied(context, action, AuditReason.STALE_VERSION)
            raise MemberVersionMismatch

        try:
            next_role, next_status = validate_transition(
                current_role=WorkspaceRole(membership.role),
                current_status=MembershipStatus(membership.status),
                mutation=mutation,
            )
        except InvalidMembershipTransition:
            await self._audit_denied(context, action, AuditReason.INVALID_STATE_TRANSITION)
            raise
        if mutation.operation is MembershipOperation.REACTIVATE and account.status != "ACTIVE":
            await self._audit_denied(context, action, AuditReason.ACCOUNT_INACTIVE)
            raise InvalidMembershipTransition

        membership.role = next_role.value
        membership.status = next_status.value
        membership.version += 1
        if mutation.operation in {
            MembershipOperation.CHANGE_ROLE,
            MembershipOperation.SUSPEND,
            MembershipOperation.REVOKE,
        }:
            await self._revoke_sessions(
                account.id,
                now,
                f"MEMBERSHIP_{mutation.operation.value}",
            )
        if mutation.operation is MembershipOperation.REVOKE:
            await self._session.execute(
                update(ActivationChallenge)
                .where(
                    ActivationChallenge.workspace_id == context.workspace_id,
                    ActivationChallenge.membership_id == membership.id,
                    ActivationChallenge.status == "ISSUED",
                )
                .values(
                    status="REVOKED",
                    revoked_at=now,
                    revoke_reason_code="MEMBERSHIP_REVOKED",
                    version=ActivationChallenge.version + 1,
                )
            )
        await self._session.flush()
        await self._audit_succeeded(context, action, membership.id)
        return await self._reference(membership, account)

    async def _require_admin(self, context: AuthorizationContext) -> None:
        row = await self._session.scalar(
            select(WorkspaceMembership.id)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.id == context.membership_id,
                WorkspaceMembership.user_account_id == context.actor_account_id,
                WorkspaceMembership.role == context.role.value,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.status == "ACTIVE",
                Workspace.status == "ACTIVE",
            )
        )
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        require_capability(context, Capability.MANAGE_MEMBERS)

    async def _reference(
        self, membership: WorkspaceMembership, account: UserAccount
    ) -> MemberReference:
        last_login_at = await self._session.scalar(
            select(func.max(AuthSession.issued_at)).where(AuthSession.user_account_id == account.id)
        )
        return MemberReference(
            id=membership.id,
            email=account.normalized_email,
            display_name=account.display_name,
            role=WorkspaceRole(membership.role),
            status=MembershipStatus(membership.status),
            account_status=account.status,
            preferred_language=account.preferred_language,
            timezone=account.timezone,
            last_login_at=last_login_at,
            created_at=membership.created_at,
            version=membership.version,
        )

    @staticmethod
    def _from_row(row: object) -> MemberReference:
        values = row  # SQLAlchemy row exposes the selected labels as attributes.
        return MemberReference(
            id=values.id,  # type: ignore[attr-defined]
            email=values.normalized_email,  # type: ignore[attr-defined]
            display_name=values.display_name,  # type: ignore[attr-defined]
            role=WorkspaceRole(values.role),  # type: ignore[attr-defined]
            status=MembershipStatus(values.status),  # type: ignore[attr-defined]
            account_status=values.account_status,  # type: ignore[attr-defined]
            preferred_language=values.preferred_language,  # type: ignore[attr-defined]
            timezone=values.timezone,  # type: ignore[attr-defined]
            last_login_at=values.last_login_at,  # type: ignore[attr-defined]
            created_at=values.created_at,  # type: ignore[attr-defined]
            version=values.version,  # type: ignore[attr-defined]
        )

    async def _revoke_sessions(self, account_id: UUID, now: datetime, reason: str) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.user_account_id == account_id, AuthSession.status == "ACTIVE")
            .values(
                status="REVOKED",
                revoked_at=now,
                revoke_reason_code=reason,
                version=AuthSession.version + 1,
            )
        )

    @staticmethod
    def _action(operation: MembershipOperation) -> AuditAction:
        return {
            MembershipOperation.CHANGE_ROLE: AuditAction.MEMBER_ROLE_CHANGED,
            MembershipOperation.SUSPEND: AuditAction.MEMBER_SUSPENDED,
            MembershipOperation.REACTIVATE: AuditAction.MEMBER_REACTIVATED,
            MembershipOperation.REVOKE: AuditAction.MEMBER_REVOKED,
        }[operation]

    async def _audit_succeeded(
        self, context: AuthorizationContext, action: AuditAction, membership_id: UUID
    ) -> None:
        await self._audit(context, action, AuditResult.SUCCEEDED, membership_id=membership_id)

    async def _audit_denied(
        self, context: AuthorizationContext, action: AuditAction, reason: AuditReason
    ) -> None:
        await self._audit(context, action, AuditResult.DENIED, reason=reason)

    async def _audit(
        self,
        context: AuthorizationContext,
        action: AuditAction,
        result: AuditResult,
        *,
        membership_id: UUID | None = None,
        reason: AuditReason | None = None,
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
                resource_type=AuditResourceType.WORKSPACE_MEMBERSHIP,
                resource_id=membership_id if result is AuditResult.SUCCEEDED else None,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.MEMBERSHIP_ADMINISTRATION,
            )
        )
