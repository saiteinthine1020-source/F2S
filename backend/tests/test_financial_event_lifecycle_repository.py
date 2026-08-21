"""PostgreSQL lifecycle conservation, isolation, concurrency, and rollback tests."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.household_finance import (
    FinancialEventLifecycleStateConflict,
    FinancialEventReplacement,
    FinancialEventVersionMismatch,
)
from app.modules.workspace_access import AuthorizationContext, AuthorizationDenied, WorkspaceRole
from tests.fixtures import seed_phase_one_workspaces


def _context(
    account: UUID, workspace: UUID, membership: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account, workspace, membership, role, uuid4())


@pytest.mark.postgres
def test_lifecycle_commands_conserve_history_and_fail_atomically(
    migrated_database: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
        admin = _context(
            fixture.admin_a_user_id,
            fixture.workspace_a_id,
            fixture.admin_a_membership_id,
            WorkspaceRole.ADMIN,
        )
        contributor = _context(
            fixture.multi_user_id,
            fixture.workspace_a_id,
            fixture.contributor_a_membership_id,
            WorkspaceRole.CONTRIBUTOR,
        )
        foreign_admin = _context(
            fixture.admin_b_user_id,
            fixture.workspace_b_id,
            fixture.admin_b_membership_id,
            WorkspaceRole.ADMIN,
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO workspace_modules (id, workspace_id, module_code, enabled) "
                        "VALUES (:id, :workspace, 'HOUSEHOLD_FINANCE', true) "
                        "ON CONFLICT (workspace_id, module_code) DO UPDATE SET enabled = true"
                    ),
                    {"id": uuid4(), "workspace": fixture.workspace_b_id},
                )

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                category = await repository.create_category(
                    admin,
                    display_name="Lifecycle expense",
                    normalized_name=f"lifecycle-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )

                async def create(amount: str) -> UUID:
                    record = await repository.create_event(
                        admin,
                        operation_id=uuid4(),
                        event_kind="MANUAL_EXPENSE",
                        cash_direction="OUTFLOW",
                        activity_classification_code="HOUSEHOLD",
                        occurred_on=date(2026, 8, 22),
                        finance_category_id=category.id,
                        amount=Decimal(amount),
                        currency_code="USD",
                        payment_method_code="CASH",
                        counterparty_text=None,
                        reference_text=None,
                        notes=None,
                    )
                    return record.id

                reversed_id = await create("25.0000")
                corrected_id = await create("40.0000")
                archived_id = await create("15.0000")
                concurrent_id = await create("12.0000")
                rollback_id = await create("9.0000")

            async with factory.begin() as session:
                result = await SqlAlchemyFinanceRepository(session).reverse_event(
                    admin,
                    event_id=reversed_id,
                    expected_version=1,
                    operation_id=uuid4(),
                    occurred_on=date(2026, 8, 23),
                    reason_code="ENTERED_IN_ERROR",
                    correction=False,
                    replacement=None,
                )
                assert result.original.posting_status == "REVERSED"
                assert result.reversal is not None
                assert result.reversal.amount == result.original.amount
                assert result.reversal.currency_code == result.original.currency_code
                assert result.reversal.cash_direction == "INFLOW"

                corrected = await SqlAlchemyFinanceRepository(session).reverse_event(
                    admin,
                    event_id=corrected_id,
                    expected_version=1,
                    operation_id=uuid4(),
                    occurred_on=date(2026, 8, 23),
                    reason_code="INCORRECT_AMOUNT",
                    correction=True,
                    replacement=FinancialEventReplacement(
                        "MANUAL_EXPENSE",
                        "OUTFLOW",
                        "HOUSEHOLD",
                        date(2026, 8, 22),
                        category.id,
                        Decimal("35.0000"),
                        "USD",
                        "CASH",
                        None,
                        None,
                        None,
                    ),
                )
                assert corrected.replacement is not None
                assert corrected.replacement.amount == Decimal("35.0000")

                archived = await SqlAlchemyFinanceRepository(session).archive_event(
                    admin,
                    event_id=archived_id,
                    expected_version=1,
                    reason_code="DUPLICATE",
                )
                assert archived.archived_at is not None
                assert archived.posting_status == "EFFECTIVE"

                with pytest.raises(AuthorizationDenied):
                    await SqlAlchemyFinanceRepository(session).archive_event(
                        contributor,
                        event_id=rollback_id,
                        expected_version=1,
                        reason_code="OTHER",
                    )
                with pytest.raises(AuthorizationDenied):
                    await SqlAlchemyFinanceRepository(session).archive_event(
                        foreign_admin,
                        event_id=rollback_id,
                        expected_version=1,
                        reason_code="OTHER",
                    )

            async def reverse_concurrently() -> str:
                async with factory.begin() as session:
                    try:
                        await SqlAlchemyFinanceRepository(session).reverse_event(
                            admin,
                            event_id=concurrent_id,
                            expected_version=1,
                            operation_id=uuid4(),
                            occurred_on=date(2026, 8, 23),
                            reason_code="DUPLICATE",
                            correction=False,
                            replacement=None,
                        )
                        return "REVERSED"
                    except (
                        FinancialEventLifecycleStateConflict,
                        FinancialEventVersionMismatch,
                    ):
                        return "CONFLICT"

            outcomes = await asyncio.gather(reverse_concurrently(), reverse_concurrently())
            assert sorted(outcomes) == ["CONFLICT", "REVERSED"]

            original_append = SqlAlchemyAuditWriter.append

            async def fail_audit(writer: SqlAlchemyAuditWriter, intent: object) -> UUID:
                del writer, intent
                raise RuntimeError("synthetic lifecycle audit failure")

            monkeypatch.setattr(SqlAlchemyAuditWriter, "append", fail_audit)
            with pytest.raises(RuntimeError, match="synthetic lifecycle audit failure"):
                async with factory.begin() as session:
                    await SqlAlchemyFinanceRepository(session).reverse_event(
                        admin,
                        event_id=rollback_id,
                        expected_version=1,
                        operation_id=uuid4(),
                        occurred_on=date(2026, 8, 23),
                        reason_code="OTHER",
                        correction=False,
                        replacement=None,
                    )
            monkeypatch.setattr(SqlAlchemyAuditWriter, "append", original_append)

            async with factory() as session:
                rollback = (
                    await session.execute(
                        text(
                            "SELECT posting_status, version FROM financial_events "
                            "WHERE workspace_id = :workspace AND id = :event"
                        ),
                        {"workspace": fixture.workspace_a_id, "event": rollback_id},
                    )
                ).one()
                assert tuple(rollback) == ("EFFECTIVE", 1)
                assert (
                    await session.scalar(
                        text(
                            "SELECT count(*) FROM financial_events WHERE workspace_id = :workspace "
                            "AND reverses_financial_event_id = :event"
                        ),
                        {"workspace": fixture.workspace_a_id, "event": rollback_id},
                    )
                    == 0
                )

                official = await session.scalar(
                    text(
                        "SELECT sum(CASE WHEN cash_direction = 'INFLOW' "
                        "THEN amount ELSE -amount END) "
                        "FROM financial_events WHERE workspace_id = :workspace "
                        "AND id = :original OR (workspace_id = :workspace "
                        "AND reverses_financial_event_id = :original)"
                    ),
                    {"workspace": fixture.workspace_a_id, "original": reversed_id},
                )
                assert official == Decimal("0.0000")

                actions = set(
                    await session.scalars(
                        text(
                            "SELECT action_code FROM audit_events WHERE workspace_id = :workspace "
                            "AND resource_id IN (:reversed, :corrected, :archived)"
                        ),
                        {
                            "workspace": fixture.workspace_a_id,
                            "reversed": reversed_id,
                            "corrected": corrected_id,
                            "archived": archived_id,
                        },
                    )
                )
                assert {
                    "FINANCIAL_EVENT_REVERSED",
                    "FINANCIAL_EVENT_CORRECTED",
                    "FINANCIAL_EVENT_ARCHIVED",
                } <= actions
        finally:
            await engine.dispose()

    asyncio.run(exercise())
