"""Framework-free membership lifecycle policy and orchestration."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.modules.workspace_access import AuthorizationContext, WorkspaceRole


class MembershipStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class MembershipOperation(StrEnum):
    CHANGE_ROLE = "CHANGE_ROLE"
    SUSPEND = "SUSPEND"
    REACTIVATE = "REACTIVATE"
    REVOKE = "REVOKE"


class MemberVersionMismatch(Exception):
    """The supplied membership version is no longer current."""


class InvalidMembershipTransition(Exception):
    """The requested lifecycle transition is not permitted from the current state."""


class OwnershipInvariantViolation(Exception):
    """Generic membership management attempted to alter Admin ownership."""


@dataclass(frozen=True, slots=True)
class MemberReference:
    id: UUID
    email: str
    display_name: str
    role: WorkspaceRole
    status: MembershipStatus
    account_status: str
    preferred_language: str
    timezone: str
    last_login_at: datetime | None
    created_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class MembershipMutation:
    operation: MembershipOperation
    role: WorkspaceRole | None = None


class MemberLifecycleRepository(Protocol):
    async def list_members(self, context: AuthorizationContext) -> tuple[MemberReference, ...]: ...

    async def mutate(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        mutation: MembershipMutation,
        now: datetime,
    ) -> MemberReference: ...


class MemberLifecycleService:
    def __init__(self, repository: MemberLifecycleRepository) -> None:
        self._repository = repository

    async def list_members(self, context: AuthorizationContext) -> tuple[MemberReference, ...]:
        return await self._repository.list_members(context)

    async def change_role(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        role: WorkspaceRole,
        now: datetime,
    ) -> MemberReference:
        if role not in {WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR}:
            raise OwnershipInvariantViolation
        return await self._mutate(
            context,
            membership_id=membership_id,
            expected_version=expected_version,
            mutation=MembershipMutation(MembershipOperation.CHANGE_ROLE, role),
            now=now,
        )

    async def suspend(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        now: datetime,
    ) -> MemberReference:
        return await self._mutate(
            context,
            membership_id=membership_id,
            expected_version=expected_version,
            mutation=MembershipMutation(MembershipOperation.SUSPEND),
            now=now,
        )

    async def reactivate(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        now: datetime,
    ) -> MemberReference:
        return await self._mutate(
            context,
            membership_id=membership_id,
            expected_version=expected_version,
            mutation=MembershipMutation(MembershipOperation.REACTIVATE),
            now=now,
        )

    async def revoke(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        now: datetime,
    ) -> MemberReference:
        return await self._mutate(
            context,
            membership_id=membership_id,
            expected_version=expected_version,
            mutation=MembershipMutation(MembershipOperation.REVOKE),
            now=now,
        )

    async def _mutate(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        mutation: MembershipMutation,
        now: datetime,
    ) -> MemberReference:
        if expected_version <= 0:
            raise MemberVersionMismatch
        return await self._repository.mutate(
            context,
            membership_id=membership_id,
            expected_version=expected_version,
            mutation=mutation,
            now=now,
        )


def validate_transition(
    *,
    current_role: WorkspaceRole,
    current_status: MembershipStatus,
    mutation: MembershipMutation,
) -> tuple[WorkspaceRole, MembershipStatus]:
    """Return the permitted next state or reject an owner/invalid transition."""
    if current_role is WorkspaceRole.ADMIN:
        raise OwnershipInvariantViolation
    if current_status is MembershipStatus.REVOKED:
        raise InvalidMembershipTransition

    if mutation.operation is MembershipOperation.CHANGE_ROLE:
        if (
            mutation.role not in {WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR}
            or mutation.role is current_role
        ):
            raise InvalidMembershipTransition
        return mutation.role, current_status
    if mutation.operation is MembershipOperation.SUSPEND:
        if current_status is not MembershipStatus.ACTIVE:
            raise InvalidMembershipTransition
        return current_role, MembershipStatus.SUSPENDED
    if mutation.operation is MembershipOperation.REACTIVATE:
        if current_status is not MembershipStatus.SUSPENDED:
            raise InvalidMembershipTransition
        return current_role, MembershipStatus.ACTIVE
    if mutation.operation is MembershipOperation.REVOKE:
        if current_status not in {
            MembershipStatus.PENDING,
            MembershipStatus.ACTIVE,
            MembershipStatus.SUSPENDED,
        }:
            raise InvalidMembershipTransition
        return current_role, MembershipStatus.REVOKED
    raise InvalidMembershipTransition
