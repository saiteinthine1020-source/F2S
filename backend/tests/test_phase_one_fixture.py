"""Release-gate contract for the canonical Phase 1 fixture pack."""

import asyncio

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.infrastructure.database.models.workspace_access import WorkspaceMembership
from app.infrastructure.database.session import create_database_engine, create_session_factory
from tests.fixtures import seed_phase_one_workspaces


@pytest.mark.postgres
def test_phase_one_fixture_has_every_role_state_and_foreign_identifier(
    migrated_database: Settings,
) -> None:
    """The shared pack cannot silently lose a required isolation dimension."""

    async def exercise() -> None:
        fixture = await seed_phase_one_workspaces(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                memberships = (
                    await session.execute(
                        select(
                            WorkspaceMembership.workspace_id,
                            WorkspaceMembership.role,
                            WorkspaceMembership.status,
                        ).where(
                            WorkspaceMembership.workspace_id.in_(
                                (fixture.workspace_a_id, fixture.workspace_b_id)
                            )
                        )
                    )
                ).all()
            assert {row.role for row in memberships} == {"ADMIN", "CONTRIBUTOR", "ADVISOR"}
            assert {row.status for row in memberships} == {
                "PENDING",
                "ACTIVE",
                "SUSPENDED",
                "REVOKED",
            }
            assert {row.workspace_id for row in memberships} == {
                fixture.workspace_a_id,
                fixture.workspace_b_id,
            }
            assert fixture.foreign_membership_id == fixture.admin_b_membership_id
            assert fixture.foreign_module_id == fixture.module_b_id
        finally:
            await engine.dispose()

    asyncio.run(exercise())
