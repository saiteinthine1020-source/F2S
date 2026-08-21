"""PostgreSQL Pending edit concurrency, audit, state, and isolation tests."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.household_finance import (
    FinancialEventStateConflict,
    FinancialEventVersionMismatch,
    PendingFinancialEventChanges,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)
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
    amount: Decimal = Decimal("10.5000"),
) -> UUID:
    record = await repository.create_event(
        context,
        operation_id=uuid4(),
        event_kind="MANUAL_EXPENSE",
        cash_direction="OUTFLOW",
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 20),
        finance_category_id=category_id,
        amount=amount,
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text="Synthetic payee",
        reference_text=None,
        notes="Original note",
    )
    return record.id


@pytest.mark.postgres
def test_pending_updates_are_versioned_attributed_and_workspace_isolated(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
        second_user_id = uuid4()
        second_membership_id = uuid4()
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
        contributor_two = _context(
            account_id=second_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=second_membership_id,
            role=WorkspaceRole.CONTRIBUTOR,
        )
        admin_b = _context(
            account_id=fixture.admin_b_user_id,
            workspace_id=fixture.workspace_b_id,
            membership_id=fixture.admin_b_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        try:
            async with engine.begin() as connection:
                suffix = uuid4().hex
                await connection.execute(
                    text(
                        "INSERT INTO user_accounts "
                        "(id, normalized_email, display_name, status, "
                        "preferred_language, timezone) "
                        "VALUES (:id, :email, 'Contributor Two', 'ACTIVE', 'en', 'UTC')"
                    ),
                    {"id": second_user_id, "email": f"contributor-two-{suffix}@example.invalid"},
                )
                await connection.execute(
                    text(
                        "INSERT INTO workspace_memberships "
                        "(id, workspace_id, user_account_id, role, status) "
                        "VALUES (:id, :workspace, :user, 'CONTRIBUTOR', 'ACTIVE')"
                    ),
                    {
                        "id": second_membership_id,
                        "workspace": fixture.workspace_a_id,
                        "user": second_user_id,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO workspace_modules "
                        "(id, workspace_id, module_code, enabled) "
                        "VALUES (:id, :workspace, 'HOUSEHOLD_FINANCE', true)"
                    ),
                    {"id": uuid4(), "workspace": fixture.workspace_b_id},
                )

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                category_a = await repository.create_category(
                    admin_a,
                    display_name="Pending edits",
                    normalized_name=f"pending-edits-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )
                own_event_id = await _create_event(
                    repository, contributor_a, category_id=category_a.id
                )
                other_event_id = await _create_event(
                    repository, contributor_two, category_id=category_a.id
                )

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                category_b = await repository.create_category(
                    admin_b,
                    display_name="Foreign pending edits",
                    normalized_name=f"foreign-pending-edits-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )
                foreign_event_id = await _create_event(
                    repository, admin_b, category_id=category_b.id
                )

            changes = PendingFinancialEventChanges(
                changed_fields=frozenset({"money", "payment_method", "notes"}),
                amount=Decimal("20.5000"),
                currency_code="USD",
                payment_method_code="BANK_TRANSFER",
                notes="Corrected note",
            )

            async def concurrent_update() -> str:
                async with factory.begin() as session:
                    try:
                        await SqlAlchemyFinanceRepository(session).update_pending_event(
                            contributor_a,
                            event_id=own_event_id,
                            expected_version=1,
                            changes=changes,
                        )
                        return "UPDATED"
                    except FinancialEventVersionMismatch:
                        return "STALE"

            outcomes = await asyncio.gather(concurrent_update(), concurrent_update())
            assert sorted(outcomes) == ["STALE", "UPDATED"]

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                with pytest.raises(AuthorizationDenied):
                    await repository.update_pending_event(
                        contributor_two,
                        event_id=own_event_id,
                        expected_version=2,
                        changes=changes,
                    )
                with pytest.raises(AuthorizationDenied):
                    await repository.update_pending_event(
                        contributor_a,
                        event_id=other_event_id,
                        expected_version=1,
                        changes=changes,
                    )
                with pytest.raises(AuthorizationDenied):
                    await repository.update_pending_event(
                        contributor_a,
                        event_id=foreign_event_id,
                        expected_version=1,
                        changes=changes,
                    )

            async with factory.begin() as session:
                await session.execute(
                    text(
                        "UPDATE financial_events SET approval_status = 'REJECTED', "
                        "reviewed_by_membership_id = :reviewer, reviewed_at = now(), "
                        "decision_reason_code = 'SYNTHETIC_REJECTION', "
                        "decision_explanation = 'Synthetic rejection evidence' "
                        "WHERE workspace_id = :workspace AND id = :event"
                    ),
                    {
                        "reviewer": fixture.admin_a_membership_id,
                        "workspace": fixture.workspace_a_id,
                        "event": own_event_id,
                    },
                )
                await session.execute(
                    text(
                        "UPDATE financial_events SET approval_status = 'APPROVED', "
                        "posting_status = 'EFFECTIVE', "
                        "reviewed_by_membership_id = :reviewer, reviewed_at = now(), "
                        "decision_reason_code = 'SYNTHETIC_APPROVAL' "
                        "WHERE workspace_id = :workspace AND id = :event"
                    ),
                    {
                        "reviewer": fixture.admin_a_membership_id,
                        "workspace": fixture.workspace_a_id,
                        "event": other_event_id,
                    },
                )

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                with pytest.raises(FinancialEventStateConflict):
                    await repository.update_pending_event(
                        contributor_a,
                        event_id=own_event_id,
                        expected_version=2,
                        changes=changes,
                    )
                with pytest.raises(FinancialEventStateConflict):
                    await repository.update_pending_event(
                        contributor_two,
                        event_id=other_event_id,
                        expected_version=1,
                        changes=changes,
                    )

            async with factory() as session:
                row = (
                    await session.execute(
                        text(
                            "SELECT amount, currency_code, payment_method_code, notes, version, "
                            "created_by_membership_id, updated_by_membership_id "
                            "FROM financial_events WHERE workspace_id = :workspace AND id = :event"
                        ),
                        {"workspace": fixture.workspace_a_id, "event": own_event_id},
                    )
                ).one()
                assert tuple(row) == (
                    Decimal("20.5000"),
                    "USD",
                    "BANK_TRANSFER",
                    "Corrected note",
                    2,
                    fixture.contributor_a_membership_id,
                    fixture.contributor_a_membership_id,
                )
                official_count = await session.scalar(
                    text(
                        "SELECT count(*) FROM financial_events "
                        "WHERE workspace_id = :workspace AND id = :event "
                        "AND approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE'"
                    ),
                    {"workspace": fixture.workspace_a_id, "event": own_event_id},
                )
                assert official_count == 0
                audit_rows = (
                    await session.execute(
                        text(
                            "SELECT action_code, result_code, reason_code, actor_membership_id "
                            "FROM audit_events WHERE workspace_id = :workspace "
                            "AND resource_type_code = 'FINANCIAL_EVENT' "
                            "AND (resource_id = :event OR action_code = 'FINANCE_ACCESS_DENIED')"
                        ),
                        {"workspace": fixture.workspace_a_id, "event": own_event_id},
                    )
                ).all()
                assert (
                    "FINANCIAL_EVENT_PENDING_UPDATED",
                    "SUCCEEDED",
                    None,
                    fixture.contributor_a_membership_id,
                ) in [tuple(row) for row in audit_rows]
                assert any(
                    row.action_code == "FINANCE_ACCESS_DENIED"
                    and row.result_code == "DENIED"
                    and row.actor_membership_id
                    in {
                        fixture.contributor_a_membership_id,
                        second_membership_id,
                    }
                    for row in audit_rows
                )

            async with factory() as session:
                history = await SqlAlchemyFinanceRepository(session).list_event_status_history(
                    contributor_a, event_id=own_event_id
                )
                assert history is not None
                assert [record.action_code for record in history] == [
                    "FINANCIAL_EVENT_SUBMITTED",
                    "FINANCIAL_EVENT_PENDING_UPDATED",
                ]
                assert all(record.actor_membership_id is not None for record in history)
        finally:
            await engine.dispose()

    asyncio.run(exercise())
