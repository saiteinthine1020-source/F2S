"""PostgreSQL financial-event filter, role, cursor, and workspace-isolation tests."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.household_finance import FinancialEventQuery
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole
from tests.fixtures import seed_phase_one_workspaces


def _context(
    *, account_id: UUID, workspace_id: UUID, membership_id: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account_id, workspace_id, membership_id, role, uuid4())


async def _create_event(
    repository: SqlAlchemyFinanceRepository,
    context: AuthorizationContext,
    *,
    category_id: UUID,
    occurred_on: date,
    amount: str,
    kind: str = "MANUAL_INCOME",
) -> UUID:
    record = await repository.create_event(
        context,
        operation_id=uuid4(),
        event_kind=kind,
        cash_direction="INFLOW" if kind == "MANUAL_INCOME" else "OUTFLOW",
        activity_classification_code="HOUSEHOLD",
        occurred_on=occurred_on,
        finance_category_id=category_id,
        amount=Decimal(amount),
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text="Synthetic query fixture",
        reference_text=None,
        notes=None,
    )
    return record.id


@pytest.mark.postgres
def test_role_scoped_filters_and_keyset_pages_are_isolated(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        admin_a = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        contributor_a = _context(
            account_id=fixture.multi_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.contributor_a_membership_id,
            role=WorkspaceRole.CONTRIBUTOR,
        )
        advisor_a = _context(
            account_id=fixture.advisor_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.advisor_a_membership_id,
            role=WorkspaceRole.ADVISOR,
        )
        admin_b = _context(
            account_id=fixture.admin_b_user_id,
            workspace_id=fixture.workspace_b_id,
            membership_id=fixture.admin_b_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        try:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "INSERT INTO workspace_modules "
                        "(id, workspace_id, module_code, enabled) "
                        "VALUES (:id, :workspace, 'HOUSEHOLD_FINANCE', true)"
                    ),
                    {"id": uuid4(), "workspace": fixture.workspace_b_id},
                )
                repository = SqlAlchemyFinanceRepository(session)
                category_a = await repository.create_category(
                    admin_a,
                    display_name="Query A",
                    normalized_name=f"query-a-{uuid4().hex}",
                    applicability_code="BOTH",
                    activity_classification_code="HOUSEHOLD",
                )
                approved_ids = tuple(
                    [
                        await _create_event(
                            repository,
                            admin_a,
                            category_id=category_a.id,
                            occurred_on=occurred_on,
                            amount=amount,
                        )
                        for occurred_on, amount in (
                            (date(2026, 8, 14), "1.0000"),
                            (date(2026, 8, 13), "2.0000"),
                            (date(2026, 8, 12), "3.0000"),
                        )
                    ]
                )
                pending_id = await _create_event(
                    repository,
                    contributor_a,
                    category_id=category_a.id,
                    occurred_on=date(2026, 8, 15),
                    amount="4.0000",
                    kind="MANUAL_EXPENSE",
                )
                category_b = await repository.create_category(
                    admin_b,
                    display_name="Query B",
                    normalized_name=f"query-b-{uuid4().hex}",
                    applicability_code="BOTH",
                    activity_classification_code="HOUSEHOLD",
                )
                foreign_id = await _create_event(
                    repository,
                    admin_b,
                    category_id=category_b.id,
                    occurred_on=date(2026, 8, 16),
                    amount="5.0000",
                )

            async with sessions() as session:
                repository = SqlAlchemyFinanceRepository(session)
                first = await repository.list_visible_events(
                    admin_a,
                    query=FinancialEventQuery(
                        approval_statuses=("APPROVED",),
                        occurred_from=date(2026, 8, 12),
                        occurred_to=date(2026, 8, 15),
                        category_ids=(category_a.id,),
                        event_kinds=("MANUAL_INCOME",),
                        cash_directions=("INFLOW",),
                        activity_classifications=("HOUSEHOLD",),
                        payment_methods=("CASH",),
                        currencies=("USD",),
                        page_size=2,
                    ),
                )
                assert tuple(record.id for record in first.records) == approved_ids[:2]
                assert first.next_position is not None
                second = await repository.list_visible_events(
                    admin_a,
                    query=FinancialEventQuery(
                        approval_statuses=("APPROVED",),
                        occurred_from=date(2026, 8, 12),
                        occurred_to=date(2026, 8, 15),
                        category_ids=(category_a.id,),
                        event_kinds=("MANUAL_INCOME",),
                        cash_directions=("INFLOW",),
                        activity_classifications=("HOUSEHOLD",),
                        payment_methods=("CASH",),
                        currencies=("USD",),
                        page_size=2,
                        after=first.next_position,
                    ),
                )
                assert tuple(record.id for record in second.records) == approved_ids[2:]
                assert second.next_position is None

                contributor_page = await repository.list_visible_events(
                    contributor_a, query=FinancialEventQuery()
                )
                assert tuple(record.id for record in contributor_page.records) == (pending_id,)
                advisor_page = await repository.list_visible_events(
                    advisor_a, query=FinancialEventQuery()
                )
                assert {record.id for record in advisor_page.records} == set(approved_ids)
                assert (
                    await repository.get_visible_event(contributor_a, event_id=approved_ids[0])
                    is None
                )
                assert await repository.get_visible_event(advisor_a, event_id=pending_id) is None
                assert await repository.get_visible_event(admin_a, event_id=foreign_id) is None

                foreign_filter = await repository.list_visible_events(
                    admin_a,
                    query=FinancialEventQuery(category_ids=(category_b.id,)),
                )
                assert foreign_filter.records == ()
        finally:
            await engine.dispose()

    asyncio.run(exercise())
