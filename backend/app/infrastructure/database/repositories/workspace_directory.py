"""SQLAlchemy account-level eligible workspace directory."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
from app.modules.workspace_access.directory import WorkspaceDirectoryRepository
from app.modules.workspace_access.repositories import (
    WorkspaceMembershipReference,
    WorkspaceReference,
)


class SqlAlchemyWorkspaceDirectoryRepository(WorkspaceDirectoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_eligible_workspaces(
        self, account_id: UUID
    ) -> tuple[WorkspaceMembershipReference, ...]:
        statement = (
            select(
                WorkspaceMembership.id.label("membership_id"),
                WorkspaceMembership.role,
                Workspace.id,
                Workspace.name,
                Workspace.type,
                Workspace.base_currency_code,
                Workspace.timezone,
                Workspace.preferred_language,
                Workspace.version,
            )
            .select_from(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.user_account_id == account_id,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.id == account_id,
                UserAccount.status == "ACTIVE",
                Workspace.status == "ACTIVE",
            )
            .order_by(Workspace.name, Workspace.id)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(
            WorkspaceMembershipReference(
                membership_id=row.membership_id,
                role=row.role,
                workspace=WorkspaceReference(
                    id=row.id,
                    name=row.name,
                    type_code=row.type,
                    base_currency_code=row.base_currency_code,
                    timezone=row.timezone,
                    preferred_language=row.preferred_language,
                    version=row.version,
                ),
            )
            for row in rows
        )
