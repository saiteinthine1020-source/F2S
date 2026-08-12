"""Two-workspace authorization-context and scoped-repository integration tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

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
from tests.fixtures import seed_phase_one_workspaces


@pytest.mark.postgres
def test_context_resolution_uses_current_multi_workspace_membership(
    migrated_database: Settings,
) -> None:
    """One account receives the independently persisted role in each selected workspace."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
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
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                with pytest.raises(AuthorizationDenied) as inactive:
                    await repository.resolve_context(
                        actor_account_id=fixture.suspended_user_id,
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
                    membership_id=fixture.contributor_a_membership_id,
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
        fixture = await seed_phase_one_workspaces(migrated_database)
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
