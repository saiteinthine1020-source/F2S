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
from app.modules.workspace_access.repositories import (
    WorkspaceAccessRepository,
    WorkspaceAdministration,
    WorkspaceModuleReference,
    WorkspaceReference,
)

__all__ = [
    "AuthorizationContext",
    "AuthorizationDenied",
    "Capability",
    "DenialCode",
    "WorkspaceRole",
    "WorkspaceAccessRepository",
    "WorkspaceAdministration",
    "WorkspaceModuleReference",
    "WorkspaceReference",
    "capabilities_for",
    "require_capability",
]
