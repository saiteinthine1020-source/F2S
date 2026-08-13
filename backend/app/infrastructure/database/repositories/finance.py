"""Workspace-scoped SQLAlchemy repository foundation for Household Finance."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.finance import FinanceCategory, FinancialEvent
from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
from app.modules.household_finance import FinanceCategoryRecord, FinancialEventRecord
from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
)


class SqlAlchemyFinanceRepository:
    """Return finance records only through a currently active selected workspace."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_category(
        self, context: AuthorizationContext, *, category_id: UUID
    ) -> FinanceCategoryRecord | None:
        await self._revalidate(context)
        category = await self._session.scalar(
            select(FinanceCategory).where(
                FinanceCategory.workspace_id == context.workspace_id,
                FinanceCategory.id == category_id,
            )
        )
        if category is None:
            return None
        return FinanceCategoryRecord(
            id=category.id,
            display_name=category.display_name,
            applicability_code=category.applicability_code,
            activity_classification_code=category.activity_classification_code,
            status=category.status,
            version=category.version,
        )

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        await self._revalidate(context)
        event = await self._session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
        )
        if event is None:
            return None
        return FinancialEventRecord(
            id=event.id,
            event_kind=event.event_kind,
            cash_direction=event.cash_direction,
            occurred_on=event.occurred_on,
            amount=event.amount,
            currency_code=event.currency_code,
            approval_status=event.approval_status,
            posting_status=event.posting_status,
            version=event.version,
        )

    async def _revalidate(self, context: AuthorizationContext) -> None:
        statement = (
            select(WorkspaceMembership.id)
            .select_from(WorkspaceMembership)
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
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
