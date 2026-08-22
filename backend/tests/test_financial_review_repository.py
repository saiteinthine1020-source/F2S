"""PostgreSQL review lifecycle, audit, immutability, and isolation tests."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.household_finance import FinancialReviewStateConflict
from app.modules.workspace_access import AuthorizationContext, AuthorizationDenied, WorkspaceRole
from tests.fixtures import seed_phase_one_workspaces


def _context(
    account: UUID, workspace: UUID, membership: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account, workspace, membership, role, uuid4())


@pytest.mark.postgres
def test_reviews_are_approved_only_attributed_audited_immutable_and_isolated(
    migrated_database: Settings,
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
        advisor = _context(
            fixture.advisor_a_user_id,
            fixture.workspace_a_id,
            fixture.advisor_a_membership_id,
            WorkspaceRole.ADVISOR,
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
                    display_name="Review expense",
                    normalized_name=f"review-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )
                approved = await repository.create_event(
                    admin,
                    operation_id=uuid4(),
                    event_kind="MANUAL_EXPENSE",
                    cash_direction="OUTFLOW",
                    activity_classification_code="HOUSEHOLD",
                    occurred_on=date(2026, 8, 22),
                    finance_category_id=category.id,
                    amount=Decimal("20.0000"),
                    currency_code="USD",
                    payment_method_code="CASH",
                    counterparty_text=None,
                    reference_text=None,
                    notes=None,
                )
                pending = await repository.create_event(
                    contributor,
                    operation_id=uuid4(),
                    event_kind="MANUAL_EXPENSE",
                    cash_direction="OUTFLOW",
                    activity_classification_code="HOUSEHOLD",
                    occurred_on=date(2026, 8, 22),
                    finance_category_id=category.id,
                    amount=Decimal("10.0000"),
                    currency_code="USD",
                    payment_method_code="CASH",
                    counterparty_text=None,
                    reference_text=None,
                    notes=None,
                )
            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                flag = await repository.create_event_review(
                    advisor,
                    event_id=approved.id,
                    operation_id=uuid4(),
                    review_kind="FLAG",
                    body_text="Confidential review body",
                    reason_code="POSSIBLE_DUPLICATE",
                )
                assert flag.created_by_membership_id == advisor.membership_id
                assert flag.flag_status == "OPEN"
                assert await repository.list_event_reviews(advisor, event_id=approved.id) == (flag,)
                assert (
                    await repository.list_event_reviews(foreign_admin, event_id=approved.id) is None
                )
                with pytest.raises(AuthorizationDenied):
                    await repository.list_event_reviews(contributor, event_id=approved.id)
                with pytest.raises(AuthorizationDenied):
                    await repository.create_event_review(
                        advisor,
                        event_id=pending.id,
                        operation_id=uuid4(),
                        review_kind="COMMENT",
                        body_text="Not permitted",
                        reason_code=None,
                    )
                resolved = await repository.resolve_event_review(
                    admin,
                    review_id=flag.id,
                    expected_version=1,
                    resolution_code="REVIEWED_NO_CHANGE",
                )
                assert resolved.flag_status == "RESOLVED" and resolved.version == 2
                with pytest.raises(FinancialReviewStateConflict):
                    await repository.resolve_event_review(
                        admin,
                        review_id=flag.id,
                        expected_version=2,
                        resolution_code="OTHER",
                    )
            async with factory() as session:
                actions = set(
                    await session.scalars(
                        text(
                            "SELECT action_code FROM audit_events "
                            "WHERE workspace_id = :workspace AND resource_id = :review"
                        ),
                        {"workspace": fixture.workspace_a_id, "review": flag.id},
                    )
                )
                assert actions == {
                    "FINANCIAL_REVIEW_FLAGGED",
                    "FINANCIAL_REVIEW_FLAG_RESOLVED",
                }
                audit_rows = (
                    await session.execute(
                        text(
                            "SELECT action_code, reason_code, context_code "
                            "FROM audit_events WHERE resource_id = :review"
                        ),
                        {"review": flag.id},
                    )
                ).all()
                audit_text = " ".join(str(value) for row in audit_rows for value in tuple(row))
                assert "Confidential review body" not in audit_text
            with pytest.raises(DBAPIError):
                async with factory.begin() as session:
                    await session.execute(
                        text("DELETE FROM financial_event_reviews WHERE id = :review"),
                        {"review": flag.id},
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())
