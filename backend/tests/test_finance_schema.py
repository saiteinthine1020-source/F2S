"""PostgreSQL constraints and scoped repository tests for Issue #79."""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Numeric, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.workspace_access.authorization import AuthorizationContext, WorkspaceRole
from tests.fixtures import seed_phase_one_workspaces


async def insert_category(
    connection: Any,
    *,
    workspace_id: UUID,
    membership_id: UUID,
    name: str,
) -> UUID:
    category_id = uuid4()
    await connection.execute(
        text(
            "INSERT INTO finance_categories "
            "(id, workspace_id, display_name, normalized_name, applicability_code, "
            "activity_classification_code, created_by_membership_id, "
            "updated_by_membership_id) VALUES "
            "(:id, :workspace, :name, :normalized, 'BOTH', 'HOUSEHOLD', :actor, :actor)"
        ),
        {
            "id": category_id,
            "workspace": workspace_id,
            "name": name,
            "normalized": name.lower(),
            "actor": membership_id,
        },
    )
    return category_id


async def insert_approved_event(
    connection: Any,
    *,
    workspace_id: UUID,
    membership_id: UUID,
    category_id: UUID,
    amount: str = "10.5000",
    currency: str = "USD",
    direction: str = "INFLOW",
    reverses_id: UUID | None = None,
) -> UUID:
    event_id = uuid4()
    event_kind = "MANUAL_INCOME" if direction == "INFLOW" else "MANUAL_EXPENSE"
    await connection.execute(
        text(
            "INSERT INTO financial_events "
            "(id, workspace_id, event_kind, cash_direction, activity_classification_code, "
            "occurred_on, finance_category_id, amount, currency_code, payment_method_code, "
            "approval_status, posting_status, reviewed_by_membership_id, reviewed_at, "
            "decision_reason_code, reverses_financial_event_id, operation_id, "
            "created_by_membership_id, updated_by_membership_id) VALUES "
            "(:id, :workspace, :kind, :direction, 'HOUSEHOLD', :occurred, :category, "
            ":amount, :currency, 'CASH', 'APPROVED', 'EFFECTIVE', :actor, :reviewed, "
            "'ADMIN_CREATED', :reverses, :operation, :actor, :actor)"
        ),
        {
            "id": event_id,
            "workspace": workspace_id,
            "kind": event_kind,
            "direction": direction,
            "occurred": date(2026, 8, 14),
            "category": category_id,
            "amount": Decimal(amount),
            "currency": currency,
            "actor": membership_id,
            "reviewed": datetime.now(UTC),
            "reverses": reverses_id,
            "operation": uuid4(),
        },
    )
    return event_id


@pytest.mark.postgres
def test_finance_schema_uses_exact_money_restrictive_fks_and_required_indexes(
    migrated_database: Settings,
) -> None:
    """The physical schema exposes the reviewed precision, history, and query paths."""
    engine = create_engine(migrated_database.database_url.set(drivername="postgresql+psycopg"))
    try:
        inspector = inspect(engine)
        amount = next(
            column
            for column in inspector.get_columns("financial_events")
            if column["name"] == "amount"
        )
        numeric = cast(Numeric[Decimal], amount["type"])
        assert numeric.precision == 24
        assert numeric.scale == 4

        for table_name in ("finance_categories", "financial_events"):
            foreign_keys = inspector.get_foreign_keys(table_name)
            assert foreign_keys
            assert all(key["options"].get("ondelete") in (None, "RESTRICT") for key in foreign_keys)

        category_indexes = {item["name"] for item in inspector.get_indexes("finance_categories")}
        event_indexes = {item["name"] for item in inspector.get_indexes("financial_events")}
        assert {
            "uq_finance_category_active_scope_name",
            "ix_finance_category_workspace_status_name",
        } <= category_indexes
        assert {
            "uq_financial_event_effective_reversal",
            "ix_financial_event_workspace_occurred",
            "ix_financial_event_workspace_state_kind_date",
            "ix_financial_event_category_date",
            "ix_financial_event_payment_date",
            "ix_financial_event_reversal_link",
            "ix_financial_event_replacement_link",
        } <= event_indexes
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_finance_repository_conceals_foreign_workspace_records(
    migrated_database: Settings,
) -> None:
    """Scoped repository identifiers cannot cross the selected workspace."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                category_a = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=f"Household A {uuid4().hex}",
                )
                category_b = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_b_id,
                    membership_id=fixture.admin_b_membership_id,
                    name=f"Household B {uuid4().hex}",
                )
                event_a = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_a,
                )
                event_b = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_b_id,
                    membership_id=fixture.admin_b_membership_id,
                    category_id=category_b,
                    currency="JPY",
                    amount="10.0000",
                )

            context = AuthorizationContext(
                actor_account_id=fixture.admin_a_user_id,
                workspace_id=fixture.workspace_a_id,
                membership_id=fixture.admin_a_membership_id,
                role=WorkspaceRole.ADMIN,
                correlation_id=uuid4(),
            )
            factory = create_session_factory(engine)
            async with factory() as session:
                repository = SqlAlchemyFinanceRepository(session)
                assert (await repository.get_category(context, category_id=category_a)) is not None
                assert await repository.get_category(context, category_id=category_b) is None
                assert (await repository.get_event(context, event_id=event_a)) is not None
                assert await repository.get_event(context, event_id=event_b) is None
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_cross_workspace_category_and_actor_references_are_rejected(
    migrated_database: Settings,
) -> None:
    """Composite foreign keys reject both foreign categories and foreign actors."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                foreign_category = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_b_id,
                    membership_id=fixture.admin_b_membership_id,
                    name=f"Foreign {uuid4().hex}",
                )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await insert_approved_event(
                        connection,
                        workspace_id=fixture.workspace_a_id,
                        membership_id=fixture.admin_a_membership_id,
                        category_id=foreign_category,
                    )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await insert_category(
                        connection,
                        workspace_id=fixture.workspace_a_id,
                        membership_id=fixture.admin_b_membership_id,
                        name=f"Foreign actor {uuid4().hex}",
                    )

            async with engine.begin() as connection:
                category_a = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=f"Local event {uuid4().hex}",
                )
                category_b = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_b_id,
                    membership_id=fixture.admin_b_membership_id,
                    name=f"Foreign event {uuid4().hex}",
                )
                event_a = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_a,
                )
                event_b = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_b_id,
                    membership_id=fixture.admin_b_membership_id,
                    category_id=category_b,
                    amount="10.0000",
                    currency="JPY",
                )
            for invalid_target in (event_a, event_b):
                with pytest.raises(IntegrityError):
                    async with engine.begin() as connection:
                        await connection.execute(
                            text(
                                "UPDATE financial_events "
                                "SET reverses_financial_event_id = :target WHERE id = :event"
                            ),
                            {"target": invalid_target, "event": event_a},
                        )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_approved_facts_and_hard_delete_are_database_protected(
    migrated_database: Settings,
) -> None:
    """Approved financial truth is append-only even through direct SQL."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                category_id = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=f"Immutable {uuid4().hex}",
                )
                event_id = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_id,
                )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text("UPDATE financial_events SET amount = 99 WHERE id = :id"),
                        {"id": event_id},
                    )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text("DELETE FROM financial_events WHERE id = :id"), {"id": event_id}
                    )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text("DELETE FROM finance_categories WHERE id = :id"), {"id": category_id}
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_reversal_constraints_reject_cross_currency_chain_and_duplicates(
    migrated_database: Settings,
) -> None:
    """Only one opposite, same-value, same-currency reversal can target an effective original."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                category_id = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=f"Reversal {uuid4().hex}",
                )
                original_id = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_id,
                )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await insert_approved_event(
                        connection,
                        workspace_id=fixture.workspace_a_id,
                        membership_id=fixture.admin_a_membership_id,
                        category_id=category_id,
                        currency="JPY",
                        amount="10.5000",
                        direction="OUTFLOW",
                        reverses_id=original_id,
                    )
            async with engine.begin() as connection:
                await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_id,
                    direction="OUTFLOW",
                    reverses_id=original_id,
                )
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await insert_approved_event(
                        connection,
                        workspace_id=fixture.workspace_a_id,
                        membership_id=fixture.admin_a_membership_id,
                        category_id=category_id,
                        direction="OUTFLOW",
                        reverses_id=original_id,
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_archived_category_remains_readable_for_historical_event(
    migrated_database: Settings,
) -> None:
    """Archival prevents active reuse without breaking the event's category reference."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                category_id = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=f"Archived {uuid4().hex}",
                )
                category_name = (
                    await connection.execute(
                        text("SELECT display_name FROM finance_categories WHERE id = :id"),
                        {"id": category_id},
                    )
                ).scalar_one()
                event_id = await insert_approved_event(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    category_id=category_id,
                )
                await connection.execute(
                    text(
                        "UPDATE finance_categories SET status = 'ARCHIVED', archived_at = :now, "
                        "archived_by_membership_id = :actor, "
                        "archive_reason_code = 'NO_LONGER_USED' "
                        "WHERE id = :id"
                    ),
                    {
                        "now": datetime.now(UTC),
                        "actor": fixture.admin_a_membership_id,
                        "id": category_id,
                    },
                )
                row = (
                    await connection.execute(
                        text(
                            "SELECT c.status FROM financial_events e "
                            "JOIN finance_categories c ON c.workspace_id = e.workspace_id "
                            "AND c.id = e.finance_category_id WHERE e.id = :id"
                        ),
                        {"id": event_id},
                    )
                ).one()
                assert row.status == "ARCHIVED"
            async with engine.begin() as connection:
                replacement_id = await insert_category(
                    connection,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                    name=category_name,
                )
                assert replacement_id != category_id
        finally:
            await engine.dispose()

    asyncio.run(exercise())
