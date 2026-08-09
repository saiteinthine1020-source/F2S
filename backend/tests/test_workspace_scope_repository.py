"""Two-workspace authorization-context and scoped-repository integration tests."""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.infrastructure.database.models.workspace_access import WorkspaceModule
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceRole,
)


@dataclass(frozen=True, slots=True)
class TwoWorkspaceFixture:
    """Identifiers for two tenants and varied membership states."""

    workspace_a_id: UUID
    workspace_b_id: UUID
    admin_a_user_id: UUID
    admin_a_membership_id: UUID
    multi_user_id: UUID
    multi_a_membership_id: UUID
    multi_b_membership_id: UUID
    inactive_user_id: UUID
    module_a_id: UUID
    module_b_id: UUID


async def seed_two_workspaces(settings: Settings) -> TwoWorkspaceFixture:
    """Create isolated workspaces, a multi-workspace actor, and an inactive membership."""
    fixture = TwoWorkspaceFixture(
        workspace_a_id=uuid4(),
        workspace_b_id=uuid4(),
        admin_a_user_id=uuid4(),
        admin_a_membership_id=uuid4(),
        multi_user_id=uuid4(),
        multi_a_membership_id=uuid4(),
        multi_b_membership_id=uuid4(),
        inactive_user_id=uuid4(),
        module_a_id=uuid4(),
        module_b_id=uuid4(),
    )
    admin_b_user_id, admin_b_membership_id = uuid4(), uuid4()
    inactive_membership_id = uuid4()
    suffix = uuid4().hex
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES "
                    "(:admin_a, :email_a, 'Admin A', 'ACTIVE', 'en', 'UTC'), "
                    "(:admin_b, :email_b, 'Admin B', 'ACTIVE', 'en', 'UTC'), "
                    "(:multi_user, :email_multi, 'Multi User', 'ACTIVE', 'en', 'UTC'), "
                    "(:inactive_user, :email_inactive, 'Inactive', 'ACTIVE', 'en', 'UTC')"
                ),
                {
                    "admin_a": fixture.admin_a_user_id,
                    "email_a": f"admin-a-{suffix}@example.invalid",
                    "admin_b": admin_b_user_id,
                    "email_b": f"admin-b-{suffix}@example.invalid",
                    "multi_user": fixture.multi_user_id,
                    "email_multi": f"multi-{suffix}@example.invalid",
                    "inactive_user": fixture.inactive_user_id,
                    "email_inactive": f"inactive-{suffix}@example.invalid",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "description, address, owner_membership_id, owner_role, "
                    "owner_membership_status, status) VALUES "
                    "(:workspace_a, 'Workspace A', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    "'Restricted A', 'Address A', :owner_a, 'ADMIN', 'ACTIVE', 'ACTIVE'), "
                    "(:workspace_b, 'Workspace B', 'FARM', 'JPY', 'Asia/Tokyo', 'ja', "
                    "'Restricted B', 'Address B', :owner_b, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {
                    "workspace_a": fixture.workspace_a_id,
                    "workspace_b": fixture.workspace_b_id,
                    "owner_a": fixture.admin_a_membership_id,
                    "owner_b": admin_b_membership_id,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) VALUES "
                    "(:owner_a, :workspace_a, :admin_a, 'ADMIN', 'ACTIVE'), "
                    "(:owner_b, :workspace_b, :admin_b, 'ADMIN', 'ACTIVE'), "
                    "(:multi_a, :workspace_a, :multi_user, 'CONTRIBUTOR', 'ACTIVE'), "
                    "(:multi_b, :workspace_b, :multi_user, 'ADVISOR', 'ACTIVE'), "
                    "(:inactive, :workspace_a, :inactive_user, 'ADVISOR', 'SUSPENDED')"
                ),
                {
                    "owner_a": fixture.admin_a_membership_id,
                    "workspace_a": fixture.workspace_a_id,
                    "admin_a": fixture.admin_a_user_id,
                    "owner_b": admin_b_membership_id,
                    "workspace_b": fixture.workspace_b_id,
                    "admin_b": admin_b_user_id,
                    "multi_a": fixture.multi_a_membership_id,
                    "multi_b": fixture.multi_b_membership_id,
                    "multi_user": fixture.multi_user_id,
                    "inactive": inactive_membership_id,
                    "inactive_user": fixture.inactive_user_id,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_modules "
                    "(id, workspace_id, module_code, enabled) VALUES "
                    "(:module_a, :workspace_a, 'HOUSEHOLD_FINANCE', true), "
                    "(:module_b, :workspace_b, 'FARMING_INVESTMENTS', false)"
                ),
                {
                    "module_a": fixture.module_a_id,
                    "workspace_a": fixture.workspace_a_id,
                    "module_b": fixture.module_b_id,
                    "workspace_b": fixture.workspace_b_id,
                },
            )
    finally:
        await engine.dispose()
    return fixture


@pytest.mark.postgres
def test_context_resolution_uses_current_multi_workspace_membership(
    migrated_database: Settings,
) -> None:
    """One account receives the independently persisted role in each selected workspace."""

    async def exercise() -> None:
        fixture = await seed_two_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                context_a = await repository.resolve_context(
                    actor_account_id=fixture.multi_user_id,
                    workspace_id=fixture.workspace_a_id,
                    correlation_id=uuid4(),
                )
                context_b = await repository.resolve_context(
                    actor_account_id=fixture.multi_user_id,
                    workspace_id=fixture.workspace_b_id,
                    correlation_id=uuid4(),
                )
                assert context_a.role is WorkspaceRole.CONTRIBUTOR
                assert context_b.role is WorkspaceRole.ADVISOR
                assert {module.id for module in await repository.list_modules(context_a)} == {
                    fixture.module_a_id
                }
                assert {module.id for module in await repository.list_modules(context_b)} == {
                    fixture.module_b_id
                }
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_inactive_foreign_and_fabricated_contexts_are_denied_safely(
    migrated_database: Settings,
) -> None:
    """Inactive and invented authority never reaches a protected workspace read."""

    async def exercise() -> None:
        fixture = await seed_two_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                with pytest.raises(AuthorizationDenied) as inactive:
                    await repository.resolve_context(
                        actor_account_id=fixture.inactive_user_id,
                        workspace_id=fixture.workspace_a_id,
                        correlation_id=uuid4(),
                    )
                assert inactive.value.code is DenialCode.MEMBERSHIP_INACTIVE

                with pytest.raises(AuthorizationDenied) as foreign:
                    await repository.resolve_context(
                        actor_account_id=fixture.admin_a_user_id,
                        workspace_id=fixture.workspace_b_id,
                        correlation_id=uuid4(),
                    )
                assert foreign.value.code is DenialCode.RESOURCE_NOT_FOUND

                fabricated = AuthorizationContext(
                    actor_account_id=fixture.multi_user_id,
                    workspace_id=fixture.workspace_a_id,
                    membership_id=fixture.multi_a_membership_id,
                    role=WorkspaceRole.ADMIN,
                    correlation_id=uuid4(),
                )
                with pytest.raises(AuthorizationDenied) as invented:
                    await repository.get_workspace(fabricated)
                assert invented.value.code is DenialCode.RESOURCE_NOT_FOUND
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_restricted_fields_and_mutations_require_admin_and_workspace_scope(
    migrated_database: Settings,
) -> None:
    """Contributor/foreign mutations disclose nothing and change no protected row."""

    async def exercise() -> None:
        fixture = await seed_two_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session, session.begin():
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                admin_context = await repository.resolve_context(
                    actor_account_id=fixture.admin_a_user_id,
                    workspace_id=fixture.workspace_a_id,
                    correlation_id=uuid4(),
                )
                contributor_context = await repository.resolve_context(
                    actor_account_id=fixture.multi_user_id,
                    workspace_id=fixture.workspace_a_id,
                    correlation_id=uuid4(),
                )

                administration = await repository.get_workspace_administration(admin_context)
                assert administration.description == "Restricted A"
                with pytest.raises(AuthorizationDenied) as restricted:
                    await repository.get_workspace_administration(contributor_context)
                assert restricted.value.code is DenialCode.PERMISSION_DENIED

                with pytest.raises(AuthorizationDenied) as contributor_write:
                    await repository.set_module_enabled(
                        contributor_context, module_id=fixture.module_a_id, enabled=False
                    )
                assert contributor_write.value.code is DenialCode.PERMISSION_DENIED

                with pytest.raises(AuthorizationDenied) as foreign_write:
                    await repository.set_module_enabled(
                        admin_context, module_id=fixture.module_b_id, enabled=True
                    )
                assert foreign_write.value.code is DenialCode.RESOURCE_NOT_FOUND

                module_rows = (
                    await session.execute(
                        select(WorkspaceModule.id, WorkspaceModule.enabled).where(
                            WorkspaceModule.id.in_((fixture.module_a_id, fixture.module_b_id))
                        )
                    )
                ).all()
                module_states: dict[UUID, bool] = {row.id: row.enabled for row in module_rows}
                assert module_states == {
                    fixture.module_a_id: True,
                    fixture.module_b_id: False,
                }

                changed = await repository.set_module_enabled(
                    admin_context, module_id=fixture.module_a_id, enabled=False
                )
                assert changed.enabled is False
                assert changed.version == 2
        finally:
            await engine.dispose()

    asyncio.run(exercise())
