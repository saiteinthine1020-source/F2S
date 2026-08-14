"""PostgreSQL manual financial-event atomicity, role, and isolation tests."""

import asyncio
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.application_support import IdempotencyKeyReused, IdempotencyService
from app.modules.household_finance import (
    ActivityClassification,
    FinanceCommandMetadata,
    FinancialEventCommandService,
    FinancialEventKind,
    ManualFinancialEventCommand,
    PaymentMethod,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    WorkspaceRole,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint
from tests.fixtures import seed_phase_one_workspaces


def _context(
    *, account_id: UUID, workspace_id: UUID, membership_id: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account_id, workspace_id, membership_id, role, uuid4())


def _metadata(operation_id: UUID, key: str, fingerprint: bytes) -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        operation_id=operation_id,
        operation=OperationCode("CREATE_FINANCIAL_EVENT"),
        idempotency_key=IdempotencyKey(key),
        request_fingerprint=RequestFingerprint.from_canonical_bytes(fingerprint),
        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
    )


def _command(
    *, category_id: UUID, kind: FinancialEventKind, amount: str
) -> ManualFinancialEventCommand:
    return ManualFinancialEventCommand(
        event_kind=kind,
        activity_classification=ActivityClassification.HOUSEHOLD,
        occurred_on=date(2026, 8, 15),
        finance_category_id=category_id,
        amount=amount,
        currency_code="USD",
        payment_method=PaymentMethod.CASH,
        counterparty="Synthetic counterparty",
        reference="SYNTHETIC-REFERENCE",
        notes="Synthetic test note",
    )


@pytest.mark.postgres
def test_admin_contributor_replay_and_audit_are_atomic(migrated_database: Settings) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
        admin = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        contributor = _context(
            account_id=fixture.multi_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.contributor_a_membership_id,
            role=WorkspaceRole.CONTRIBUTOR,
        )
        admin_operation = uuid4()
        contributor_operation = uuid4()
        try:
            async with factory.begin() as session:
                category = await SqlAlchemyFinanceRepository(session).create_category(
                    admin,
                    display_name="Manual events",
                    normalized_name=f"manual-events-{uuid4().hex}",
                    applicability_code="BOTH",
                    activity_classification_code="HOUSEHOLD",
                )

            async with factory.begin() as session:
                service = FinancialEventCommandService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                )
                approved, replayed = await service.create_manual(
                    admin,
                    command=_command(
                        category_id=category.id,
                        kind=FinancialEventKind.MANUAL_INCOME,
                        amount="10.50",
                    ),
                    metadata=_metadata(admin_operation, "admin-event-key-0001", b"admin income"),
                )
                assert not replayed
                assert approved.approval_status == "APPROVED"
                assert approved.posting_status == "EFFECTIVE"

            async with factory.begin() as session:
                service = FinancialEventCommandService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                )
                pending, replayed = await service.create_manual(
                    contributor,
                    command=_command(
                        category_id=category.id,
                        kind=FinancialEventKind.MANUAL_EXPENSE,
                        amount="3.25",
                    ),
                    metadata=_metadata(
                        contributor_operation,
                        "contributor-key-0001",
                        b"contributor expense",
                    ),
                )
                assert not replayed
                assert pending.approval_status == "PENDING"
                assert pending.posting_status == "NOT_EFFECTIVE"

            async with factory.begin() as session:
                service = FinancialEventCommandService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                )
                replay, replayed = await service.create_manual(
                    contributor,
                    command=_command(
                        category_id=category.id,
                        kind=FinancialEventKind.MANUAL_EXPENSE,
                        amount="3.25",
                    ),
                    metadata=_metadata(
                        contributor_operation,
                        "contributor-key-0001",
                        b"contributor expense",
                    ),
                )
                assert replayed
                assert replay.id == pending.id
                with pytest.raises(IdempotencyKeyReused):
                    await service.create_manual(
                        contributor,
                        command=_command(
                            category_id=category.id,
                            kind=FinancialEventKind.MANUAL_EXPENSE,
                            amount="4.25",
                        ),
                        metadata=_metadata(
                            contributor_operation,
                            "contributor-key-0001",
                            b"changed expense",
                        ),
                    )

            async with factory() as session:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "(SELECT count(*) FROM financial_events "
                            "WHERE workspace_id = :workspace), "
                            "(SELECT count(*) FROM idempotency_records "
                            "WHERE workspace_id = :workspace AND state = 'COMPLETED')"
                        ),
                        {"workspace": fixture.workspace_a_id},
                    )
                ).one()
                assert tuple(counts) == (2, 2)
                actions = set(
                    (
                        await session.execute(
                            text(
                                "SELECT action_code FROM audit_events "
                                "WHERE workspace_id = :workspace "
                                "AND resource_type_code = 'FINANCIAL_EVENT'"
                            ),
                            {"workspace": fixture.workspace_a_id},
                        )
                    ).scalars()
                )
                assert {
                    "FINANCIAL_EVENT_CREATED_APPROVED",
                    "FINANCIAL_EVENT_SUBMITTED",
                } <= actions
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_advisor_and_foreign_category_create_no_event_or_idempotency(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
        admin = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        advisor = _context(
            account_id=fixture.advisor_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.advisor_a_membership_id,
            role=WorkspaceRole.ADVISOR,
        )
        advisor_operation = uuid4()
        foreign_operation = uuid4()
        try:
            async with engine.begin() as connection:
                foreign_category = uuid4()
                await connection.execute(
                    text(
                        "INSERT INTO finance_categories "
                        "(id, workspace_id, display_name, normalized_name, applicability_code, "
                        "activity_classification_code, created_by_membership_id, "
                        "updated_by_membership_id) VALUES "
                        "(:id, :workspace, 'Foreign', :name, 'BOTH', 'HOUSEHOLD', :actor, :actor)"
                    ),
                    {
                        "id": foreign_category,
                        "workspace": fixture.workspace_b_id,
                        "name": f"foreign-{uuid4().hex}",
                        "actor": fixture.admin_b_membership_id,
                    },
                )

            async with factory.begin() as session:
                service = FinancialEventCommandService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                )
                with pytest.raises(AuthorizationDenied):
                    await service.create_manual(
                        advisor,
                        command=_command(
                            category_id=foreign_category,
                            kind=FinancialEventKind.MANUAL_EXPENSE,
                            amount="1.00",
                        ),
                        metadata=_metadata(advisor_operation, "advisor-event-key-001", b"advisor"),
                    )

            async with factory.begin() as session:
                service = FinancialEventCommandService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                )
                with pytest.raises(AuthorizationDenied):
                    await service.create_manual(
                        admin,
                        command=_command(
                            category_id=foreign_category,
                            kind=FinancialEventKind.MANUAL_EXPENSE,
                            amount="1.00",
                        ),
                        metadata=_metadata(foreign_operation, "foreign-event-key-001", b"foreign"),
                    )

            async with factory() as session:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "(SELECT count(*) FROM financial_events WHERE operation_id IN "
                            "(:advisor, :foreign)), "
                            "(SELECT count(*) FROM idempotency_records WHERE operation_id IN "
                            "(:advisor, :foreign))"
                        ),
                        {"advisor": advisor_operation, "foreign": foreign_operation},
                    )
                ).one()
                assert tuple(counts) == (0, 0)
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_required_audit_failure_rolls_back_event_and_idempotency(
    migrated_database: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
        admin = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        operation_id = uuid4()
        try:
            async with factory.begin() as session:
                category = await SqlAlchemyFinanceRepository(session).create_category(
                    admin,
                    display_name="Rollback event",
                    normalized_name=f"rollback-event-{uuid4().hex}",
                    applicability_code="INCOME",
                    activity_classification_code="HOUSEHOLD",
                )

            async def reject_audit(writer: SqlAlchemyAuditWriter, intent: object) -> UUID:
                del writer, intent
                raise RuntimeError("synthetic audit failure")

            monkeypatch.setattr(SqlAlchemyAuditWriter, "append", reject_audit)
            with pytest.raises(RuntimeError, match="synthetic audit failure"):
                async with factory.begin() as session:
                    await FinancialEventCommandService(
                        SqlAlchemyFinanceRepository(session),
                        IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                    ).create_manual(
                        admin,
                        command=_command(
                            category_id=category.id,
                            kind=FinancialEventKind.MANUAL_INCOME,
                            amount="5.00",
                        ),
                        metadata=_metadata(
                            operation_id, "rollback-event-key-01", b"rollback event"
                        ),
                    )

            async with factory() as session:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "(SELECT count(*) FROM financial_events WHERE operation_id = "
                            ":operation), "
                            "(SELECT count(*) FROM idempotency_records WHERE operation_id = "
                            ":operation)"
                        ),
                        {"operation": operation_id},
                    )
                ).one()
                assert tuple(counts) == (0, 0)
        finally:
            await engine.dispose()

    asyncio.run(exercise())
