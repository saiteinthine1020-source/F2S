"""PostgreSQL Admin decision locking, audit, rollback, and isolation tests."""

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.application_support import IdempotencyService
from app.modules.household_finance import (
    ApprovalReasonCode,
    FinanceCommandMetadata,
    FinancialEventDecision,
    FinancialEventDecisionCommand,
    FinancialEventDecisionService,
    FinancialEventStateConflict,
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


async def _pending_event(
    repository: SqlAlchemyFinanceRepository,
    context: AuthorizationContext,
    *,
    category_id: UUID,
) -> UUID:
    record = await repository.create_event(
        context,
        operation_id=uuid4(),
        event_kind="MANUAL_EXPENSE",
        cash_direction="OUTFLOW",
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 21),
        finance_category_id=category_id,
        amount=Decimal("25.0000"),
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text="Synthetic shop",
        reference_text=None,
        notes=None,
    )
    return record.id


def _metadata(*, operation_id: UUID, marker: str) -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        operation_id=operation_id,
        operation=OperationCode("APPROVE_FINANCIAL_EVENT"),
        idempotency_key=IdempotencyKey(f"decision-{marker}-{operation_id.hex}"),
        request_fingerprint=RequestFingerprint.from_canonical_bytes(
            f"decision:{marker}:{operation_id}".encode("ascii")
        ),
        required_capability=Capability.APPROVE_OR_REJECT_SUBMISSIONS,
    )


@pytest.mark.postgres
def test_admin_decisions_are_atomic_attributed_and_official_once(
    migrated_database: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        factory = create_session_factory(engine)
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
        admin_b = _context(
            account_id=fixture.admin_b_user_id,
            workspace_id=fixture.workspace_b_id,
            membership_id=fixture.admin_b_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO workspace_modules "
                        "(id, workspace_id, module_code, enabled) "
                        "VALUES (:id, :workspace, 'HOUSEHOLD_FINANCE', true) "
                        "ON CONFLICT (workspace_id, module_code) DO UPDATE SET enabled = true"
                    ),
                    {"id": uuid4(), "workspace": fixture.workspace_b_id},
                )

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                category = await repository.create_category(
                    admin_a,
                    display_name="Admin decision test",
                    normalized_name=f"admin-decision-{uuid4().hex}",
                    applicability_code="EXPENSE",
                    activity_classification_code="HOUSEHOLD",
                )
                approved_id = await _pending_event(
                    repository, contributor_a, category_id=category.id
                )
                rejected_id = await _pending_event(
                    repository, contributor_a, category_id=category.id
                )
                concurrent_id = await _pending_event(
                    repository, contributor_a, category_id=category.id
                )
                rollback_id = await _pending_event(
                    repository, contributor_a, category_id=category.id
                )

            approved_operation_id = uuid4()
            approved_metadata = _metadata(operation_id=approved_operation_id, marker="approved")
            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                approved, replayed = await FinancialEventDecisionService(
                    repository,
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                ).decide(
                    admin_a,
                    event_id=approved_id,
                    command=FinancialEventDecisionCommand(
                        FinancialEventDecision.APPROVE,
                        ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
                    ),
                    metadata=approved_metadata,
                )
                rejected = await repository.decide_pending_event(
                    admin_a,
                    event_id=rejected_id,
                    approval_status="REJECTED",
                    posting_status="NOT_EFFECTIVE",
                    reason_code="INSUFFICIENT_EVIDENCE",
                    explanation="The supporting receipt is not readable.",
                )
                assert not replayed
                assert (approved.approval_status, approved.posting_status) == (
                    "APPROVED",
                    "EFFECTIVE",
                )
                assert (rejected.approval_status, rejected.posting_status) == (
                    "REJECTED",
                    "NOT_EFFECTIVE",
                )

            async with factory.begin() as session:
                approved_replay, replayed = await FinancialEventDecisionService(
                    SqlAlchemyFinanceRepository(session),
                    IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                ).decide(
                    admin_a,
                    event_id=approved_id,
                    command=FinancialEventDecisionCommand(
                        FinancialEventDecision.APPROVE,
                        ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
                    ),
                    metadata=approved_metadata,
                )
                assert replayed
                assert approved_replay.version == 2

            async def decide_concurrently(approval: bool) -> str:
                async with factory.begin() as session:
                    try:
                        await SqlAlchemyFinanceRepository(session).decide_pending_event(
                            admin_a,
                            event_id=concurrent_id,
                            approval_status="APPROVED" if approval else "REJECTED",
                            posting_status="EFFECTIVE" if approval else "NOT_EFFECTIVE",
                            reason_code=(
                                "REVIEWED_AND_CONFIRMED" if approval else "INCORRECT_AMOUNT"
                            ),
                            explanation=None if approval else "The amount is incorrect.",
                        )
                        return "APPROVED" if approval else "REJECTED"
                    except FinancialEventStateConflict:
                        return "CONFLICT"

            outcomes = await asyncio.gather(decide_concurrently(True), decide_concurrently(False))
            assert outcomes.count("CONFLICT") == 1
            assert len({*outcomes} & {"APPROVED", "REJECTED"}) == 1
            winning_decision = next(outcome for outcome in outcomes if outcome != "CONFLICT")

            async with factory.begin() as session:
                repository = SqlAlchemyFinanceRepository(session)
                with pytest.raises(AuthorizationDenied):
                    await repository.decide_pending_event(
                        contributor_a,
                        event_id=rollback_id,
                        approval_status="APPROVED",
                        posting_status="EFFECTIVE",
                        reason_code="REVIEWED_AND_CONFIRMED",
                        explanation=None,
                    )
                with pytest.raises(AuthorizationDenied):
                    await repository.decide_pending_event(
                        admin_b,
                        event_id=rollback_id,
                        approval_status="APPROVED",
                        posting_status="EFFECTIVE",
                        reason_code="REVIEWED_AND_CONFIRMED",
                        explanation=None,
                    )

            original_append = SqlAlchemyAuditWriter.append

            async def fail_audit(writer: SqlAlchemyAuditWriter, intent: object) -> UUID:
                del writer, intent
                raise RuntimeError("synthetic audit failure")

            monkeypatch.setattr(SqlAlchemyAuditWriter, "append", fail_audit)
            rollback_operation_id = uuid4()
            with pytest.raises(RuntimeError, match="synthetic audit failure"):
                async with factory.begin() as session:
                    await FinancialEventDecisionService(
                        SqlAlchemyFinanceRepository(session),
                        IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
                    ).decide(
                        admin_a,
                        event_id=rollback_id,
                        command=FinancialEventDecisionCommand(
                            FinancialEventDecision.APPROVE,
                            ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
                        ),
                        metadata=_metadata(operation_id=rollback_operation_id, marker="rollback"),
                    )
            monkeypatch.setattr(SqlAlchemyAuditWriter, "append", original_append)

            async with factory() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT id, approval_status, posting_status, version, "
                                "reviewed_by_membership_id, decision_reason_code, "
                                "decision_explanation FROM financial_events "
                                "WHERE workspace_id = :workspace AND id IN "
                                "(:approved, :rejected, :concurrent, :rollback)"
                            ),
                            {
                                "workspace": fixture.workspace_a_id,
                                "approved": approved_id,
                                "rejected": rejected_id,
                                "concurrent": concurrent_id,
                                "rollback": rollback_id,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
                by_id = {row["id"]: row for row in rows}
                assert by_id[approved_id]["version"] == 2
                assert by_id[approved_id]["reviewed_by_membership_id"] == (
                    fixture.admin_a_membership_id
                )
                assert by_id[rejected_id]["decision_explanation"] == (
                    "The supporting receipt is not readable."
                )
                assert (
                    by_id[rollback_id]["approval_status"],
                    by_id[rollback_id]["posting_status"],
                    by_id[rollback_id]["version"],
                ) == ("PENDING", "NOT_EFFECTIVE", 1)
                rollback_claims = await session.scalar(
                    text(
                        "SELECT count(*) FROM idempotency_records "
                        "WHERE workspace_id = :workspace AND operation_id = :operation"
                    ),
                    {
                        "workspace": fixture.workspace_a_id,
                        "operation": rollback_operation_id,
                    },
                )
                assert rollback_claims == 0

                official_ids = set(
                    await session.scalars(
                        text(
                            "SELECT id FROM financial_events WHERE workspace_id = :workspace "
                            "AND id IN (:approved, :rejected, :concurrent, :rollback) "
                            "AND approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE'"
                        ),
                        {
                            "workspace": fixture.workspace_a_id,
                            "approved": approved_id,
                            "rejected": rejected_id,
                            "concurrent": concurrent_id,
                            "rollback": rollback_id,
                        },
                    )
                )
                assert approved_id in official_ids
                assert rejected_id not in official_ids
                assert rollback_id not in official_ids
                assert (concurrent_id in official_ids) == (winning_decision == "APPROVED")

                decision_audits = (
                    await session.execute(
                        text(
                            "SELECT action_code, result_code, actor_membership_id, reason_code "
                            "FROM audit_events WHERE workspace_id = :workspace "
                            "AND resource_id IN (:approved, :rejected, :concurrent)"
                        ),
                        {
                            "workspace": fixture.workspace_a_id,
                            "approved": approved_id,
                            "rejected": rejected_id,
                            "concurrent": concurrent_id,
                        },
                    )
                ).all()
                assert (
                    "FINANCIAL_EVENT_APPROVED",
                    "SUCCEEDED",
                    fixture.admin_a_membership_id,
                    None,
                ) in [tuple(row) for row in decision_audits]
                assert (
                    "FINANCIAL_EVENT_REJECTED",
                    "SUCCEEDED",
                    fixture.admin_a_membership_id,
                    None,
                ) in [tuple(row) for row in decision_audits]
        finally:
            await engine.dispose()

    asyncio.run(exercise())
