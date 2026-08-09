"""Account-level eligible workspace directory contracts and orchestration."""

from typing import Protocol
from uuid import UUID

from app.modules.workspace_access.repositories import WorkspaceMembershipReference


class WorkspaceDirectoryRepository(Protocol):
    """Port for listing workspaces before a selected-workspace context exists."""

    async def list_eligible_workspaces(
        self, account_id: UUID
    ) -> tuple[WorkspaceMembershipReference, ...]: ...


class WorkspaceDirectoryService:
    def __init__(self, repository: WorkspaceDirectoryRepository) -> None:
        self._repository = repository

    async def list_for_account(self, account_id: UUID) -> tuple[WorkspaceMembershipReference, ...]:
        return await self._repository.list_eligible_workspaces(account_id)
