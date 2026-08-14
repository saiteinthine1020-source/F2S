"""PostgreSQL idempotency replay, concurrency, retention, and isolation tests."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.repositories.idempotency import (
    SqlAlchemyIdempotencyRepository,
)
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyKeyReused,
    SafeOutcome,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    WorkspaceRole,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint
from tests.fixtures import seed_phase_one_workspaces


async def _insert_category(session: object, *, workspace_id: UUID, membership_id: UUID) -> UUID:
    category_id = uuid4()
    await session.execute(  # type: ignore[attr-defined]
        text(
            "INSERT INTO finance_categories "
            "(id, workspace_id, display_name, normalized_name, applicability_code, "
            "activity_classification_code, created_by_membership_id, updated_by_membership_id) "
            "VALUES (:id, :workspace, 'Idempotency', :name, 'BOTH', 'HOUSEHOLD', :actor, :actor)"
        ),
        {
            "id": category_id,
            "workspace": workspace_id,
            "name": f"idempotency-{category_id.hex}",
            "actor": membership_id,
        },
    )
    return category_id


async def _insert_event(
    session: object,
    *,
    event_id: UUID,
    operation_id: UUID,
    workspace_id: UUID,
    membership_id: UUID,
    category_id: UUID,
) -> None:
    await session.execute(  # type: ignore[attr-defined]
        text(
            "INSERT INTO financial_events "
            "(id, workspace_id, event_kind, cash_direction, activity_classification_code, "
            "occurred_on, finance_category_id, amount, currency_code, payment_method_code, "
            "approval_status, posting_status, reviewed_by_membership_id, reviewed_at, "
            "decision_reason_code, operation_id, created_by_membership_id, "
            "updated_by_membership_id) VALUES "
            "(:id, :workspace, 'MANUAL_INCOME', 'INFLOW', 'HOUSEHOLD', :occurred, "
            ":category, 10.0000, 'USD', 'CASH', 'APPROVED', 'EFFECTIVE', :actor, :now, "
            "'ADMIN_CREATED', :operation, :actor, :actor)"
        ),
        {
            "id": event_id,
            "workspace": workspace_id,
            "occurred": date(2026, 8, 15),
            "category": category_id,
            "actor": membership_id,
            "now": datetime.now(UTC),
            "operation": operation_id,
        },
    )


def _context(
    *, account_id: UUID, workspace_id: UUID, membership_id: UUID, role: WorkspaceRole
) -> AuthorizationContext:
    return AuthorizationContext(account_id, workspace_id, membership_id, role, uuid4())


@pytest.mark.postgres
def test_concurrent_duplicate_commits_one_event_and_replays_safe_outcome(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        session_factory = create_session_factory(engine)
        context = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        operation_id = uuid4()
        operation = OperationCode("CREATE_FINANCIAL_EVENT")
        key = IdempotencyKey("concurrent-key-0001")
        fingerprint = RequestFingerprint.from_canonical_bytes(b"same-canonical-request")
        try:
            async with session_factory.begin() as session:
                category_id = await _insert_category(
                    session,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                )

            async def worker() -> tuple[ClaimDisposition, UUID | None]:
                async with session_factory.begin() as session:
                    repository = SqlAlchemyIdempotencyRepository(session)
                    claim = await repository.claim(
                        context,
                        operation_id=operation_id,
                        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                        operation=operation,
                        key=key,
                        fingerprint=fingerprint,
                    )
                    event_id: UUID | None = None
                    if claim.disposition is ClaimDisposition.STARTED:
                        assert claim.lease_token is not None
                        event_id = uuid4()
                        await _insert_event(
                            session,
                            event_id=event_id,
                            operation_id=operation_id,
                            workspace_id=fixture.workspace_a_id,
                            membership_id=fixture.admin_a_membership_id,
                            category_id=category_id,
                        )
                        await repository.complete(
                            context,
                            required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                            claim_id=claim.id,
                            lease_token=claim.lease_token,
                            outcome=SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", event_id, 1),
                        )
                    return claim.disposition, event_id

            results = await asyncio.gather(worker(), worker())
            assert [item[0] for item in results].count(ClaimDisposition.STARTED) == 1
            assert [item[0] for item in results].count(ClaimDisposition.REPLAY) == 1
            event_id = next(item[1] for item in results if item[1] is not None)

            async with session_factory.begin() as session:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "(SELECT count(*) FROM financial_events "
                            "WHERE operation_id = :operation), "
                            "(SELECT count(*) FROM idempotency_records "
                            "WHERE operation_id = :operation)"
                        ),
                        {"operation": operation_id},
                    )
                ).one()
                assert tuple(counts) == (1, 1)
                replay = await SqlAlchemyIdempotencyRepository(session).claim(
                    context,
                    operation_id=operation_id,
                    required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert replay.disposition is ClaimDisposition.REPLAY
                assert replay.outcome == SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", event_id, 1)
                with pytest.raises(IdempotencyKeyReused):
                    await SqlAlchemyIdempotencyRepository(session).claim(
                        context,
                        operation_id=operation_id,
                        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                        operation=operation,
                        key=key,
                        fingerprint=RequestFingerprint.from_canonical_bytes(b"changed"),
                    )

                stored_key = (
                    await session.execute(
                        text(
                            "SELECT key_digest FROM idempotency_records "
                            "WHERE operation_id = :operation"
                        ),
                        {"operation": operation_id},
                    )
                ).scalar_one()
                assert stored_key != key.value
                assert len(stored_key) == 64
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_in_progress_expiry_workspace_scope_and_lost_permission(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        session_factory = create_session_factory(engine)
        base = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
        operation = OperationCode("CREATE_FINANCIAL_EVENT")
        key = IdempotencyKey("lifecycle-key-0001")
        fingerprint = RequestFingerprint.from_canonical_bytes(b"lifecycle")
        operation_id = uuid4()
        contributor = _context(
            account_id=fixture.multi_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.contributor_a_membership_id,
            role=WorkspaceRole.CONTRIBUTOR,
        )
        try:
            async with session_factory.begin() as session:
                repository = SqlAlchemyIdempotencyRepository(session, clock=lambda: base)
                started = await repository.claim(
                    contributor,
                    operation_id=operation_id,
                    required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert started.disposition is ClaimDisposition.STARTED

            async with session_factory.begin() as session:
                active = await SqlAlchemyIdempotencyRepository(
                    session, clock=lambda: base + timedelta(minutes=1)
                ).claim(
                    contributor,
                    operation_id=operation_id,
                    required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert active.disposition is ClaimDisposition.IN_PROGRESS

            async with session_factory.begin() as session:
                stale = await SqlAlchemyIdempotencyRepository(
                    session, clock=lambda: base + timedelta(minutes=3)
                ).claim(
                    contributor,
                    operation_id=operation_id,
                    required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert stale.disposition is ClaimDisposition.RECOVERY_REQUIRED

            foreign = _context(
                account_id=fixture.admin_b_user_id,
                workspace_id=fixture.workspace_b_id,
                membership_id=fixture.admin_b_membership_id,
                role=WorkspaceRole.ADMIN,
            )
            async with session_factory.begin() as session:
                separate = await SqlAlchemyIdempotencyRepository(session, clock=lambda: base).claim(
                    foreign,
                    operation_id=operation_id,
                    required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert separate.disposition is ClaimDisposition.STARTED

            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE workspace_memberships SET status = 'SUSPENDED' "
                        "WHERE id = :membership"
                    ),
                    {"membership": fixture.contributor_a_membership_id},
                )
            async with session_factory.begin() as session:
                with pytest.raises(AuthorizationDenied):
                    await SqlAlchemyIdempotencyRepository(session).claim(
                        contributor,
                        operation_id=operation_id,
                        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                        operation=operation,
                        key=key,
                        fingerprint=fingerprint,
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_terminal_outcome_is_retained_fourteen_days_then_expires(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        session_factory = create_session_factory(engine)
        base = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
        context = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        operation_id = uuid4()
        operation = OperationCode("ARCHIVE_FINANCIAL_EVENT")
        key = IdempotencyKey("retention-key-0001")
        fingerprint = RequestFingerprint.from_canonical_bytes(b"retention")
        try:
            async with session_factory.begin() as session:
                repository = SqlAlchemyIdempotencyRepository(session, clock=lambda: base)
                claim = await repository.claim(
                    context,
                    operation_id=operation_id,
                    required_capability=Capability.MANAGE_FINANCE_CATEGORIES,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert claim.lease_token is not None
                await repository.complete(
                    context,
                    required_capability=Capability.MANAGE_FINANCE_CATEGORIES,
                    claim_id=claim.id,
                    lease_token=claim.lease_token,
                    outcome=SafeOutcome("ARCHIVED", 200),
                )

            async with session_factory.begin() as session:
                retained = await SqlAlchemyIdempotencyRepository(
                    session, clock=lambda: base + timedelta(days=13)
                ).claim(
                    context,
                    operation_id=operation_id,
                    required_capability=Capability.MANAGE_FINANCE_CATEGORIES,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert retained.disposition is ClaimDisposition.REPLAY

            async with session_factory.begin() as session:
                renewed = await SqlAlchemyIdempotencyRepository(
                    session, clock=lambda: base + timedelta(days=14, seconds=1)
                ).claim(
                    context,
                    operation_id=operation_id,
                    required_capability=Capability.MANAGE_FINANCE_CATEGORIES,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                )
                assert renewed.disposition is ClaimDisposition.STARTED
                assert renewed.id != retained.id
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_canonical_event_and_terminal_outcome_roll_back_together(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        session_factory = create_session_factory(engine)
        context = _context(
            account_id=fixture.admin_a_user_id,
            workspace_id=fixture.workspace_a_id,
            membership_id=fixture.admin_a_membership_id,
            role=WorkspaceRole.ADMIN,
        )
        operation_id = uuid4()
        event_id = uuid4()
        try:
            async with session_factory.begin() as session:
                category_id = await _insert_category(
                    session,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.admin_a_membership_id,
                )

            with pytest.raises(RuntimeError, match="synthetic response failure"):
                async with session_factory.begin() as session:
                    repository = SqlAlchemyIdempotencyRepository(session)
                    claim = await repository.claim(
                        context,
                        operation_id=operation_id,
                        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                        operation=OperationCode("CREATE_FINANCIAL_EVENT"),
                        key=IdempotencyKey("rollback-key-00001"),
                        fingerprint=RequestFingerprint.from_canonical_bytes(b"rollback"),
                    )
                    assert claim.lease_token is not None
                    await _insert_event(
                        session,
                        event_id=event_id,
                        operation_id=operation_id,
                        workspace_id=fixture.workspace_a_id,
                        membership_id=fixture.admin_a_membership_id,
                        category_id=category_id,
                    )
                    await repository.complete(
                        context,
                        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                        claim_id=claim.id,
                        lease_token=claim.lease_token,
                        outcome=SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", event_id, 1),
                    )
                    raise RuntimeError("synthetic response failure")

            async with session_factory() as session:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "(SELECT count(*) FROM financial_events "
                            "WHERE operation_id = :operation), "
                            "(SELECT count(*) FROM idempotency_records "
                            "WHERE operation_id = :operation)"
                        ),
                        {"operation": operation_id},
                    )
                ).one()
                assert tuple(counts) == (0, 0)
        finally:
            await engine.dispose()

    asyncio.run(exercise())
