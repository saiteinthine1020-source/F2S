"""Framework-free ports and projections for protected workspace persistence."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.workspace_access.authorization import AuthorizationContext
from app.modules.workspace_access.configuration import ModuleCode, WorkspaceType


class WorkspaceVersionMismatch(Exception):
    """The supplied If-Match version no longer identifies current settings."""


@dataclass(frozen=True, slots=True)
class WorkspaceReference:
    """Non-administrative workspace fields safe for every active member."""

    id: UUID
    name: str
    type_code: str
    base_currency_code: str
    timezone: str
    preferred_language: str
    version: int


@dataclass(frozen=True, slots=True)
class WorkspaceAdministration:
    """Workspace profile fields available only to the settings capability."""

    id: UUID
    description: str | None
    address: str | None
    business_category_code: str | None
    farm_type_code: str | None
    version: int


@dataclass(frozen=True, slots=True)
class WorkspaceModuleReference:
    """One selected-workspace module configuration record."""

    id: UUID
    module_code: str
    enabled: bool
    version: int


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipReference:
    """One Active workspace available to the authenticated account."""

    membership_id: UUID
    role: str
    workspace: WorkspaceReference


@dataclass(frozen=True, slots=True)
class WorkspaceSettingsSnapshot:
    """Complete Admin settings snapshot used for validated optimistic mutation."""

    workspace: WorkspaceReference
    administration: WorkspaceAdministration
    modules: tuple[WorkspaceModuleReference, ...]


@dataclass(frozen=True, slots=True)
class DesiredWorkspaceSettings:
    """Validated complete settings state; omitted-field merging happens in the service."""

    name: str
    workspace_type: WorkspaceType
    base_currency_code: str
    timezone: str
    preferred_language: str
    description: str | None
    address: str | None
    business_category_code: str | None
    farm_type_code: str | None
    modules: tuple[tuple[ModuleCode, bool], ...]


class WorkspaceAccessRepository(Protocol):
    """Port whose protected operations always require explicit authority."""

    async def resolve_context(
        self, *, actor_account_id: UUID, workspace_id: UUID, correlation_id: UUID
    ) -> AuthorizationContext:
        """Derive current authority from persisted account and membership state."""
        ...

    async def get_workspace(self, context: AuthorizationContext) -> WorkspaceReference:
        """Load a non-administrative selected-workspace projection."""
        ...

    async def get_workspace_administration(
        self, context: AuthorizationContext
    ) -> WorkspaceAdministration:
        """Load restricted settings fields for a capable actor."""
        ...

    async def list_modules(
        self, context: AuthorizationContext
    ) -> tuple[WorkspaceModuleReference, ...]:
        """List only selected-workspace module flags."""
        ...

    async def set_module_enabled(
        self, context: AuthorizationContext, *, module_id: UUID, enabled: bool
    ) -> WorkspaceModuleReference:
        """Apply one capability-checked, workspace-scoped module mutation."""
        ...

    async def update_settings(
        self,
        context: AuthorizationContext,
        *,
        expected_version: int,
        desired: DesiredWorkspaceSettings,
    ) -> WorkspaceSettingsSnapshot: ...
