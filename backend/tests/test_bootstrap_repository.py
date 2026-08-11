"""PostgreSQL single-winner and atomic bootstrap integration tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity import BootstrapState, UserAccount
from app.infrastructure.database.models.workspace_access import (
    Workspace,
    WorkspaceMembership,
    WorkspaceModule,
)
from app.infrastructure.database.repositories.bootstrap import SqlAlchemyBootstrapRepository
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.main import create_app
from app.modules.audit.events import AuditEventIntent
from app.modules.audit.ports import AuditWriter
from app.modules.bootstrap.service import (
    BootstrapCommand,
    BootstrapResult,
    BootstrapService,
    BootstrapUnavailable,
    WorkspaceType,
)
from app.modules.identity_security import Argon2idPasswordService, PasswordDigest, SecretText


class FailingAuditWriter(AuditWriter):
    async def append(self, intent: AuditEventIntent) -> UUID:
        del intent
        raise RuntimeError("synthetic audit failure")


def bootstrap_command(email: str, correlation_id: UUID | None = None) -> BootstrapCommand:
    return BootstrapCommand(
        display_name="Synthetic Bootstrap Admin",
        email=email,
        password=SecretText("synthetic-bootstrap-password"),
        account_language="en",
        account_timezone="UTC",
        workspace_name="Synthetic Bootstrap Workspace",
        workspace_type=WorkspaceType.FARM,
        base_currency_code="USD",
        workspace_language="en",
        workspace_timezone="Asia/Tokyo",
        correlation_id=correlation_id or uuid4(),
    )


async def clear_bootstrap_data(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, workspace_modules, workspace_memberships, "
                    "workspaces, user_accounts, bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.postgres
def test_bootstrap_rolls_back_when_required_audit_fails(migrated_database: Settings) -> None:
    async def exercise() -> None:
        await clear_bootstrap_data(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)

        def factory(session: AsyncSession) -> AuditWriter:
            del session
            return FailingAuditWriter()

        try:
            with pytest.raises(RuntimeError, match="synthetic audit failure"):
                async with transactional_session(sessions) as session:
                    repository = SqlAlchemyBootstrapRepository(session, factory)
                    await BootstrapService(repository, Argon2idPasswordService()).complete(
                        bootstrap_command("rollback@example.invalid")
                    )
            async with sessions() as session:
                for model in (
                    BootstrapState,
                    UserAccount,
                    Workspace,
                    WorkspaceMembership,
                    WorkspaceModule,
                    AuditEvent,
                ):
                    count = await session.scalar(select(func.count()).select_from(model))
                    assert count == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_concurrent_bootstrap_has_one_complete_owner_and_permanent_closure(
    migrated_database: Settings,
) -> None:
    async def exercise() -> BootstrapResult:
        await clear_bootstrap_data(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)

        async def attempt(index: int) -> BootstrapResult:
            async with transactional_session(sessions) as session:
                service = BootstrapService(
                    SqlAlchemyBootstrapRepository(session), Argon2idPasswordService()
                )
                return await service.complete(bootstrap_command(f"winner-{index}@example.invalid"))

        try:
            outcomes = await asyncio.gather(attempt(1), attempt(2), return_exceptions=True)
            winners = [outcome for outcome in outcomes if isinstance(outcome, BootstrapResult)]
            losers = [outcome for outcome in outcomes if isinstance(outcome, BootstrapUnavailable)]
            assert len(winners) == 1
            assert len(losers) == 1
            winner = winners[0]

            async with sessions() as session:
                account = await session.get(UserAccount, winner.account_id)
                workspace = await session.get(Workspace, winner.workspace_id)
                membership = await session.get(WorkspaceMembership, winner.membership_id)
                modules = (
                    await session.scalars(
                        select(WorkspaceModule).where(
                            WorkspaceModule.workspace_id == winner.workspace_id
                        )
                    )
                ).all()
                audits = (
                    await session.scalars(
                        select(AuditEvent).where(AuditEvent.workspace_id == winner.workspace_id)
                    )
                ).all()
                state = await session.scalar(select(BootstrapState))

                assert account is not None
                assert account.password_digest is not None
                assert account.password_digest != "synthetic-bootstrap-password"
                assert (
                    Argon2idPasswordService()
                    .verify(
                        SecretText("synthetic-bootstrap-password"),
                        PasswordDigest(account.password_digest),
                    )
                    .matches
                )
                assert workspace is not None
                assert workspace.owner_membership_id == winner.membership_id
                assert membership is not None
                assert (membership.role, membership.status) == ("ADMIN", "ACTIVE")
                assert {(module.module_code, module.enabled) for module in modules} == {
                    ("HOUSEHOLD_FINANCE", True),
                    ("FARMING_INVESTMENTS", True),
                }
                assert {event.action_code for event in audits} == {
                    "BOOTSTRAP_COMPLETED",
                    "WORKSPACE_CREATED",
                }
                assert len({event.correlation_id for event in audits}) == 1
                assert state is not None and state.completed_at is not None

            with pytest.raises(BootstrapUnavailable):
                async with transactional_session(sessions) as session:
                    await BootstrapService(
                        SqlAlchemyBootstrapRepository(session), Argon2idPasswordService()
                    ).complete(bootstrap_command("later@example.invalid"))
            return winner
        finally:
            await engine.dispose()

    winner = asyncio.run(exercise())
    correlation_id = str(uuid4())
    with TestClient(create_app(migrated_database)) as client:
        availability = client.get(
            "/api/v1/setup/bootstrap", headers={"X-Correlation-ID": correlation_id}
        )
        later = client.post(
            "/api/v1/setup/bootstrap",
            headers={
                "Origin": migrated_database.frontend_origin,
                "X-Correlation-ID": correlation_id,
            },
            json={
                "display_name": "Later Attempt",
                "email": "later@example.invalid",
                "password": "synthetic-bootstrap-password",
                "account_language": "en",
                "account_timezone": "UTC",
                "workspace_name": "Later Workspace",
                "workspace_type": "HOUSEHOLD",
                "base_currency_code": "USD",
                "workspace_language": "en",
                "workspace_timezone": "UTC",
            },
        )

    assert availability.status_code == 200
    assert availability.json() == {"data": {"available": False}}
    assert availability.headers["X-Correlation-ID"] == correlation_id
    assert availability.headers["Cache-Control"] == "no-store"
    assert later.status_code == 409
    assert later.json()["error"]["code"] == "CONFLICT"
    assert later.json()["error"]["correlation_id"] == correlation_id
    assert str(winner.workspace_id) not in later.text

    asyncio.run(clear_bootstrap_data(migrated_database))
