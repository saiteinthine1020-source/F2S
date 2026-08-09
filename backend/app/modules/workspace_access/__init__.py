"""Workspace Access domain contracts and capability policy."""

from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    capabilities_for,
    require_capability,
)
from app.modules.workspace_access.configuration import (
    MODULE_DEFAULTS,
    ModuleCode,
    WorkspaceType,
)
from app.modules.workspace_access.directory import (
    WorkspaceDirectoryRepository,
    WorkspaceDirectoryService,
)
from app.modules.workspace_access.repositories import (
    DesiredWorkspaceSettings,
    WorkspaceAccessRepository,
    WorkspaceAdministration,
    WorkspaceMembershipReference,
    WorkspaceModuleReference,
    WorkspaceReference,
    WorkspaceSettingsSnapshot,
    WorkspaceVersionMismatch,
)
from app.modules.workspace_access.settings import (
    ModuleSetting,
    SelectedWorkspace,
    WorkspaceSettingsPatch,
    WorkspaceSettingsService,
)

__all__ = [
    "AuthorizationContext",
    "AuthorizationDenied",
    "Capability",
    "DenialCode",
    "DesiredWorkspaceSettings",
    "MODULE_DEFAULTS",
    "ModuleCode",
    "ModuleSetting",
    "SelectedWorkspace",
    "WorkspaceRole",
    "WorkspaceType",
    "WorkspaceAccessRepository",
    "WorkspaceDirectoryRepository",
    "WorkspaceDirectoryService",
    "WorkspaceAdministration",
    "WorkspaceModuleReference",
    "WorkspaceMembershipReference",
    "WorkspaceReference",
    "WorkspaceSettingsSnapshot",
    "WorkspaceSettingsPatch",
    "WorkspaceSettingsService",
    "capabilities_for",
    "require_capability",
    "WorkspaceVersionMismatch",
]
