"""Framework-free workspace authorization context and capability policy."""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID


class WorkspaceRole(StrEnum):
    """The only Phase 1 workspace membership roles."""

    ADMIN = "ADMIN"
    CONTRIBUTOR = "CONTRIBUTOR"
    ADVISOR = "ADVISOR"


class Capability(StrEnum):
    """Backend-owned Phase 1 permission vocabulary."""

    ACCESS_WORKSPACE = "ACCESS_WORKSPACE"
    VIEW_OFFICIAL_BALANCES = "VIEW_OFFICIAL_BALANCES"
    VIEW_REPORTS = "VIEW_REPORTS"
    CREATE_FINANCIAL_SUBMISSION = "CREATE_FINANCIAL_SUBMISSION"
    EDIT_OWN_PENDING_SUBMISSION = "EDIT_OWN_PENDING_SUBMISSION"
    APPROVE_OR_REJECT_SUBMISSIONS = "APPROVE_OR_REJECT_SUBMISSIONS"
    COMMENT_OR_FLAG = "COMMENT_OR_FLAG"
    MANAGE_WORKSPACE_SETTINGS = "MANAGE_WORKSPACE_SETTINGS"
    MANAGE_MEMBERS = "MANAGE_MEMBERS"
    TRANSFER_OWNERSHIP = "TRANSFER_OWNERSHIP"


_ADMIN_CAPABILITIES = frozenset(Capability)
_CONTRIBUTOR_CAPABILITIES = frozenset(
    {
        Capability.ACCESS_WORKSPACE,
        Capability.CREATE_FINANCIAL_SUBMISSION,
        Capability.EDIT_OWN_PENDING_SUBMISSION,
    }
)
_ADVISOR_CAPABILITIES = frozenset(
    {
        Capability.ACCESS_WORKSPACE,
        Capability.VIEW_OFFICIAL_BALANCES,
        Capability.VIEW_REPORTS,
        Capability.COMMENT_OR_FLAG,
    }
)

CAPABILITIES_BY_ROLE: Final = MappingProxyType(
    {
        WorkspaceRole.ADMIN: _ADMIN_CAPABILITIES,
        WorkspaceRole.CONTRIBUTOR: _CONTRIBUTOR_CAPABILITIES,
        WorkspaceRole.ADVISOR: _ADVISOR_CAPABILITIES,
    }
)


class DenialCode(StrEnum):
    """Stable safe outcomes that never include a protected identifier."""

    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    MEMBERSHIP_INACTIVE = "MEMBERSHIP_INACTIVE"
    WORKSPACE_INACTIVE = "WORKSPACE_INACTIVE"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class AuthorizationDenied(Exception):
    """A safe authorization failure with no resource-specific message."""

    def __init__(self, code: DenialCode) -> None:
        self.code = code
        super().__init__(code.value)


def capabilities_for(role: WorkspaceRole) -> frozenset[Capability]:
    """Return the immutable server-owned capability set for a role."""
    return CAPABILITIES_BY_ROLE[role]


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Immutable server-derived authority for one actor and selected workspace."""

    actor_account_id: UUID
    workspace_id: UUID
    membership_id: UUID
    role: WorkspaceRole
    correlation_id: UUID
    capabilities: frozenset[Capability] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", capabilities_for(self.role))

    def permits(self, capability: Capability) -> bool:
        """Return whether this role carries the declared capability."""
        return capability in self.capabilities


def require_capability(context: AuthorizationContext, capability: Capability) -> None:
    """Raise one safe denial when the current role lacks a capability."""
    if not context.permits(capability):
        raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
