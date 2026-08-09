"""PostgreSQL workspace list, isolation, settings, module, and ETag tests."""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceModule
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.infrastructure.database.repositories.workspace_directory import (
    SqlAlchemyWorkspaceDirectoryRepository,
)
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.workspace_access import (
    AuthorizationDenied,
    DenialCode,
    ModuleCode,
    ModuleSetting,
    WorkspaceSettingsPatch,
    WorkspaceSettingsService,
    WorkspaceType,
    WorkspaceVersionMismatch,
)


@dataclass(frozen=True, slots=True)
class Fixture:
    workspace_a: UUID
    workspace_b: UUID
    admin_a: UUID
    admin_a_membership: UUID
    contributor: UUID
    contributor_a_membership: UUID


async def _clear(settings: Settings) -> None:
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


async def _seed(settings: Settings) -> Fixture:
    fixture = Fixture(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(), uuid4())
    admin_b, admin_b_membership, suspended_membership = uuid4(), uuid4(), uuid4()
    suffix = uuid4().hex
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES (:admin_a, :email_a, 'Admin A', 'ACTIVE', 'en', 'UTC'), "
                    "(:admin_b, :email_b, 'Admin B', 'ACTIVE', 'ja', 'Asia/Tokyo'), "
                    "(:contributor, :email_c, 'Contributor', 'ACTIVE', 'en', 'UTC')"
                ),
                {
                    "admin_a": fixture.admin_a,
                    "email_a": f"settings-admin-a-{suffix}@example.invalid",
                    "admin_b": admin_b,
                    "email_b": f"settings-admin-b-{suffix}@example.invalid",
                    "contributor": fixture.contributor,
                    "email_c": f"settings-contributor-{suffix}@example.invalid",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "description, owner_membership_id, owner_role, owner_membership_status, "
                    "status) VALUES "
                    "(:a, 'Workspace A', 'HOUSEHOLD', 'USD', 'UTC', 'en', 'Private A', "
                    ":owner_a, 'ADMIN', 'ACTIVE', 'ACTIVE'), "
                    "(:b, 'Workspace B', 'FARM', 'JPY', 'Asia/Tokyo', 'ja', 'Private B', "
                    ":owner_b, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {
                    "a": fixture.workspace_a,
                    "b": fixture.workspace_b,
                    "owner_a": fixture.admin_a_membership,
                    "owner_b": admin_b_membership,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) VALUES "
                    "(:owner_a, :a, :admin_a, 'ADMIN', 'ACTIVE'), "
                    "(:owner_b, :b, :admin_b, 'ADMIN', 'ACTIVE'), "
                    "(:contributor_a, :a, :contributor, 'CONTRIBUTOR', 'ACTIVE'), "
                    "(:suspended_b, :b, :contributor, 'ADVISOR', 'SUSPENDED')"
                ),
                {
                    "owner_a": fixture.admin_a_membership,
                    "a": fixture.workspace_a,
                    "admin_a": fixture.admin_a,
                    "owner_b": admin_b_membership,
                    "b": fixture.workspace_b,
                    "admin_b": admin_b,
                    "contributor_a": fixture.contributor_a_membership,
                    "contributor": fixture.contributor,
                    "suspended_b": suspended_membership,
                },
            )
            module_rows = []
            for workspace_id in (fixture.workspace_a, fixture.workspace_b):
                for code in ModuleCode:
                    module_rows.append(
                        {
                            "id": uuid4(),
                            "workspace_id": workspace_id,
                            "code": code.value,
                            "enabled": code is ModuleCode.HOUSEHOLD_FINANCE,
                        }
                    )
            await connection.execute(
                text(
                    "INSERT INTO workspace_modules "
                    "(id, workspace_id, module_code, enabled) "
                    "VALUES (:id, :workspace_id, :code, :enabled)"
                ),
                module_rows,
            )
    finally:
        await engine.dispose()
    return fixture


@pytest.mark.postgres
def test_list_and_selected_workspace_enforce_active_membership_and_isolation(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        fixture = await _seed(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            async with sessions() as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                listed = await SqlAlchemyWorkspaceDirectoryRepository(
                    session
                ).list_eligible_workspaces(fixture.contributor)
                assert len(listed) == 1
                assert listed[0].workspace.id == fixture.workspace_a
                assert listed[0].role == "CONTRIBUTOR"

                contributor = await repository.resolve_context(
                    actor_account_id=fixture.contributor,
                    workspace_id=fixture.workspace_a,
                    correlation_id=uuid4(),
                )
                selected = await WorkspaceSettingsService(repository).get_selected(contributor)
                assert selected.administration is None
                assert {module.module_code for module in selected.modules} == {
                    code.value for code in ModuleCode
                }
                with pytest.raises(AuthorizationDenied) as inactive:
                    await repository.resolve_context(
                        actor_account_id=fixture.contributor,
                        workspace_id=fixture.workspace_b,
                        correlation_id=uuid4(),
                    )
                assert inactive.value.code is DenialCode.MEMBERSHIP_INACTIVE
                with pytest.raises(AuthorizationDenied) as foreign:
                    await repository.resolve_context(
                        actor_account_id=fixture.admin_a,
                        workspace_id=fixture.workspace_b,
                        correlation_id=uuid4(),
                    )
                assert foreign.value.code is DenialCode.RESOURCE_NOT_FOUND
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_admin_update_is_stable_versioned_audited_and_preserves_module_rows(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        fixture = await _seed(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            async with transactional_session(sessions) as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                context = await repository.resolve_context(
                    actor_account_id=fixture.admin_a,
                    workspace_id=fixture.workspace_a,
                    correlation_id=uuid4(),
                )
                updated = await WorkspaceSettingsService(repository).update(
                    context,
                    expected_version=1,
                    patch=WorkspaceSettingsPatch(
                        provided=frozenset(
                            {
                                "name",
                                "workspace_type",
                                "farm_type_code",
                                "modules",
                            }
                        ),
                        name="  Renamed Workspace  ",
                        workspace_type=WorkspaceType.COMBINED,
                        farm_type_code="rice_farm",
                        modules=(
                            ModuleSetting(ModuleCode.HOUSEHOLD_FINANCE, False),
                            ModuleSetting(ModuleCode.FARMING_INVESTMENTS, True),
                        ),
                    ),
                )
                assert updated.workspace.id == fixture.workspace_a
                assert updated.workspace.name == "Renamed Workspace"
                assert updated.workspace.version == 2
                assert updated.administration.farm_type_code == "RICE_FARM"
                assert {module.module_code: module.enabled for module in updated.modules} == {
                    "FARMING_INVESTMENTS": True,
                    "HOUSEHOLD_FINANCE": False,
                }

            async with transactional_session(sessions) as session:
                repository = SqlAlchemyWorkspaceAccessRepository(session)
                context = await repository.resolve_context(
                    actor_account_id=fixture.admin_a,
                    workspace_id=fixture.workspace_a,
                    correlation_id=uuid4(),
                )
                with pytest.raises(WorkspaceVersionMismatch):
                    await WorkspaceSettingsService(repository).update(
                        context,
                        expected_version=1,
                        patch=WorkspaceSettingsPatch(
                            provided=frozenset({"name"}), name="Stale overwrite"
                        ),
                    )

            async with sessions() as session:
                workspace = await session.get(Workspace, fixture.workspace_a)
                other = await session.get(Workspace, fixture.workspace_b)
                modules = (
                    await session.scalars(
                        select(WorkspaceModule).where(
                            WorkspaceModule.workspace_id == fixture.workspace_a
                        )
                    )
                ).all()
                actions = (
                    await session.execute(
                        select(AuditEvent.action_code, AuditEvent.result_code).where(
                            AuditEvent.workspace_id == fixture.workspace_a
                        )
                    )
                ).all()
                assert workspace is not None and workspace.id == fixture.workspace_a
                assert workspace.name == "Renamed Workspace"
                assert other is not None and other.name == "Workspace B"
                assert len(modules) == 2
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(WorkspaceModule)
                        .where(WorkspaceModule.workspace_id == fixture.workspace_a)
                    )
                    == 2
                )
                assert ("WORKSPACE_SETTINGS_UPDATED", "SUCCEEDED") in actions
                assert ("WORKSPACE_RENAMED", "SUCCEEDED") in actions
                assert ("WORKSPACE_MODULES_UPDATED", "SUCCEEDED") in actions
                assert ("WORKSPACE_SETTINGS_UPDATED", "DENIED") in actions
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
