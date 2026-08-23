"""PostgreSQL receipt authorization, lifecycle, isolation, audit, and history tests."""

import asyncio
import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.receipts import SqlAlchemyReceiptRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole
from tests.fixtures import seed_phase_one_workspaces


def _context(
    account: UUID, workspace: UUID, membership: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account, workspace, membership, role, uuid4())


@pytest.mark.postgres
def test_receipt_lifecycle_is_workspace_scoped_append_only_and_safely_audited(
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
        contributor = _context(
            fixture.multi_user_id,
            fixture.workspace_a_id,
            fixture.contributor_a_membership_id,
            WorkspaceRole.CONTRIBUTOR,
        )
        advisor = _context(
            fixture.advisor_a_user_id,
            fixture.workspace_a_id,
            fixture.advisor_a_membership_id,
            WorkspaceRole.ADVISOR,
        )
        foreign = _context(
            fixture.admin_b_user_id,
            fixture.workspace_b_id,
            fixture.admin_b_membership_id,
            WorkspaceRole.ADMIN,
        )
        content = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF"
        digest = hashlib.sha256(content).hexdigest()
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
                finance = SqlAlchemyFinanceRepository(session)
                category = await finance.create_category(
                    admin,
                    display_name="Receipt expense",
                    normalized_name=f"receipt-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )

                async def create(context: AuthorizationContext) -> UUID:
                    return (
                        await finance.create_event(
                            context,
                            operation_id=uuid4(),
                            event_kind="MANUAL_EXPENSE",
                            cash_direction="OUTFLOW",
                            activity_classification_code="HOUSEHOLD",
                            occurred_on=date(2026, 8, 23),
                            finance_category_id=category.id,
                            amount=Decimal("10.0000"),
                            currency_code="USD",
                            payment_method_code="CASH",
                            counterparty_text=None,
                            reference_text=None,
                            notes=None,
                        )
                    ).id

                approved_id = await create(admin)
                pending_id = await create(contributor)

            async with factory.begin() as session:
                receipts = SqlAlchemyReceiptRepository(session)
                reserved = await receipts.reserve(
                    admin,
                    event_id=approved_id,
                    operation_id=uuid4(),
                    filename="receipt.pdf",
                    media_type="application/pdf",
                    expected_size=len(content),
                    expected_sha256=digest,
                    storage_key="a" * 64,
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                )
                pending_receipt = await receipts.reserve(
                    contributor,
                    event_id=pending_id,
                    operation_id=uuid4(),
                    filename="own.pdf",
                    media_type="application/pdf",
                    expected_size=len(content),
                    expected_sha256=digest,
                    storage_key="b" * 64,
                    expires_at=datetime.now(UTC) + timedelta(minutes=15),
                )
                expired_receipt = await receipts.reserve(
                    admin,
                    event_id=approved_id,
                    operation_id=uuid4(),
                    filename="expired.pdf",
                    media_type="application/pdf",
                    expected_size=len(content),
                    expected_sha256=digest,
                    storage_key="c" * 64,
                    expires_at=datetime.now(UTC) - timedelta(seconds=1),
                )
                assert await receipts.list_receipts(advisor, event_id=approved_id) == (reserved,)
                assert await receipts.list_receipts(advisor, event_id=pending_id) is None
                assert await receipts.list_receipts(foreign, event_id=approved_id) is None
                assert await receipts.list_receipts(contributor, event_id=pending_id) == (
                    pending_receipt,
                )

                quarantined = await receipts.mark_quarantined(
                    admin,
                    receipt_id=reserved.id,
                    actual_size=len(content),
                    actual_sha256=digest,
                    detected_media_type="application/pdf",
                )
                assert quarantined.receipt.state == "QUARANTINED"
                assert await receipts.get_for_download(advisor, receipt_id=reserved.id) is None
                available = await receipts.mark_available(admin, receipt_id=reserved.id)
                assert available.receipt.state == "AVAILABLE"
                assert await receipts.get_for_download(advisor, receipt_id=reserved.id) is not None
                removed = await receipts.remove(
                    admin,
                    event_id=approved_id,
                    receipt_id=reserved.id,
                    operation_id=uuid4(),
                    reason_code="REPLACED",
                )
                assert removed.id == reserved.id
                assert await receipts.get_for_download(advisor, receipt_id=reserved.id) is None
                assert await receipts.get_for_upload(foreign, receipt_id=pending_receipt.id) is None
                due = await receipts.due_for_cleanup(now=datetime.now(UTC))
                assert expired_receipt.id in {item.receipt.id for item in due}
                await receipts.mark_deleted(receipt_id=expired_receipt.id, now=datetime.now(UTC))

            async with factory() as session:
                actions = set(
                    await session.scalars(
                        text("SELECT action_code FROM audit_events WHERE resource_id = :receipt"),
                        {"receipt": reserved.id},
                    )
                )
                assert {
                    "FINANCIAL_RECEIPT_RESERVED",
                    "FINANCIAL_RECEIPT_LINKED",
                    "FINANCIAL_RECEIPT_QUARANTINED",
                    "FINANCIAL_RECEIPT_AVAILABLE",
                    "FINANCIAL_RECEIPT_REMOVED",
                } <= actions
                evidence = " ".join(
                    str(value)
                    for row in (
                        await session.execute(
                            text(
                                "SELECT action_code, reason_code, context_code "
                                "FROM audit_events WHERE resource_id = :receipt"
                            ),
                            {"receipt": reserved.id},
                        )
                    ).all()
                    for value in tuple(row)
                )
                assert "receipt.pdf" not in evidence and digest not in evidence
                expired_state = await session.scalar(
                    text("SELECT state FROM protected_files WHERE id = :receipt"),
                    {"receipt": expired_receipt.id},
                )
                assert expired_state == "DELETED"

            with pytest.raises(DBAPIError):
                async with factory.begin() as session:
                    await session.execute(
                        text("DELETE FROM protected_files WHERE id = :receipt"),
                        {"receipt": reserved.id},
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())
