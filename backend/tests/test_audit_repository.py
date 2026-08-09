"""PostgreSQL tests for transaction-bound append-only audit writes."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.workspace_access import Workspace
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.audit.events import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)


@dataclass(frozen=True, slots=True)
class AuditFixture:
    account_id: UUID
    workspace_id: UUID
    membership_id: UUID


async def seed_audit_fixture(settings: Settings) -> AuditFixture:
    """Create a synthetic active owner identity for audit reference tests."""
    fixture = AuditFixture(uuid4(), uuid4(), uuid4())
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES (:id, :email, 'Audit Owner', 'ACTIVE', 'en', 'UTC')"
                ),
                {"id": fixture.account_id, "email": f"audit-{uuid4().hex}@example.invalid"},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "owner_membership_id, owner_role, owner_membership_status, status) "
                    "VALUES (:id, 'Audit Workspace', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    ":membership_id, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {"id": fixture.workspace_id, "membership_id": fixture.membership_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) "
                    "VALUES (:id, :workspace_id, :account_id, 'ADMIN', 'ACTIVE')"
                ),
                {
                    "id": fixture.membership_id,
                    "workspace_id": fixture.workspace_id,
                    "account_id": fixture.account_id,
                },
            )
    finally:
        await engine.dispose()
    return fixture


@pytest.mark.postgres
def test_global_and_workspace_events_preserve_safe_fields(migrated_database: Settings) -> None:
    """Identity and workspace evidence persist with UTC server time and one correlation."""

    async def exercise() -> None:
        fixture = await seed_audit_fixture(migrated_database)
        correlation_id = uuid4()
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            async with transactional_session(sessions) as session:
                writer = SqlAlchemyAuditWriter(session)
                global_id = await writer.append(
                    AuditEventIntent(
                        scope=AuditScope.GLOBAL,
                        actor=AuditActor.user(fixture.account_id),
                        action=AuditAction.LOGIN_SUCCEEDED,
                        module=AuditModule.IDENTITY_SECURITY,
                        result=AuditResult.SUCCEEDED,
                        correlation_id=correlation_id,
                        source=AuditSource.API,
                        context=AuditContext.AUTHENTICATION,
                    )
                )
                workspace_id = await writer.append(
                    AuditEventIntent(
                        scope=AuditScope.WORKSPACE,
                        workspace_id=fixture.workspace_id,
                        actor=AuditActor.user(fixture.account_id, fixture.membership_id),
                        action=AuditAction.WORKSPACE_RENAMED,
                        module=AuditModule.WORKSPACE_ACCESS,
                        result=AuditResult.SUCCEEDED,
                        correlation_id=correlation_id,
                        resource_type=AuditResourceType.WORKSPACE,
                        resource_id=fixture.workspace_id,
                        source=AuditSource.API,
                        context=AuditContext.WORKSPACE_SETTINGS,
                    )
                )

            async with sessions() as session:
                events = (
                    await session.scalars(
                        select(AuditEvent)
                        .where(AuditEvent.id.in_((global_id, workspace_id)))
                        .order_by(AuditEvent.scope_code)
                    )
                ).all()
                assert len(events) == 2
                assert {event.correlation_id for event in events} == {correlation_id}
                assert events[0].scope_code == "GLOBAL"
                assert events[0].workspace_id is None
                assert events[0].actor_membership_id is None
                assert events[1].scope_code == "WORKSPACE"
                assert events[1].workspace_id == fixture.workspace_id
                assert events[1].actor_membership_id == fixture.membership_id
                assert all(event.occurred_at.utcoffset() == timedelta(0) for event in events)
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_state_and_required_audit_commit_or_roll_back_together(
    migrated_database: Settings,
) -> None:
    """The writer flushes in, but never commits outside, the caller transaction."""

    async def exercise() -> None:
        fixture = await seed_audit_fixture(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        correlation_id = uuid4()
        failed_action = AuditAction.WORKSPACE_RENAMED
        try:
            with pytest.raises(IntegrityError):
                async with transactional_session(sessions) as session:
                    await session.execute(
                        update(Workspace)
                        .where(Workspace.id == fixture.workspace_id)
                        .values(name="Must Roll Back")
                    )
                    await SqlAlchemyAuditWriter(session).append(
                        AuditEventIntent(
                            scope=AuditScope.WORKSPACE,
                            workspace_id=fixture.workspace_id,
                            actor=AuditActor.user(fixture.account_id, uuid4()),
                            action=failed_action,
                            module=AuditModule.WORKSPACE_ACCESS,
                            result=AuditResult.SUCCEEDED,
                            correlation_id=correlation_id,
                        )
                    )

            async with sessions() as session:
                name = await session.scalar(
                    select(Workspace.name).where(Workspace.id == fixture.workspace_id)
                )
                failed_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.correlation_id == correlation_id)
                )
                assert name == "Audit Workspace"
                assert failed_count == 0

            async with transactional_session(sessions) as session:
                await session.execute(
                    update(Workspace)
                    .where(Workspace.id == fixture.workspace_id)
                    .values(name="Committed Rename")
                )
                event_id = await SqlAlchemyAuditWriter(session).append(
                    AuditEventIntent(
                        scope=AuditScope.WORKSPACE,
                        workspace_id=fixture.workspace_id,
                        actor=AuditActor.user(fixture.account_id, fixture.membership_id),
                        action=AuditAction.WORKSPACE_RENAMED,
                        module=AuditModule.WORKSPACE_ACCESS,
                        result=AuditResult.SUCCEEDED,
                        correlation_id=correlation_id,
                        resource_type=AuditResourceType.WORKSPACE,
                        resource_id=fixture.workspace_id,
                    )
                )

            async with sessions() as session:
                assert (
                    await session.scalar(
                        select(Workspace.name).where(Workspace.id == fixture.workspace_id)
                    )
                    == "Committed Rename"
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(AuditEvent)
                        .where(AuditEvent.id == event_id)
                    )
                    == 1
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_denied_foreign_access_stores_no_foreign_reference(migrated_database: Settings) -> None:
    """Concealed denials preserve actor/correlation but not a probed workspace identifier."""

    async def exercise() -> None:
        fixture = await seed_audit_fixture(migrated_database)
        correlation_id = uuid4()
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            async with transactional_session(sessions) as session:
                event_id = await SqlAlchemyAuditWriter(session).append(
                    AuditEventIntent.denied_cross_workspace(
                        actor_account_id=fixture.account_id,
                        correlation_id=correlation_id,
                        source=AuditSource.API,
                    )
                )
            async with sessions() as session:
                event = await session.get(AuditEvent, event_id)
                assert event is not None
                assert event.scope_code == "GLOBAL"
                assert event.workspace_id is None
                assert event.resource_type_code == "WORKSPACE"
                assert event.resource_id is None
                assert event.reason_code == AuditReason.RESOURCE_NOT_FOUND.value
                assert event.correlation_id == correlation_id
        finally:
            await engine.dispose()

    asyncio.run(exercise())
