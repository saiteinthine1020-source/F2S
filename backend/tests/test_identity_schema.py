"""Identity and workspace access relational invariant tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.infrastructure.database.session import create_database_engine


async def insert_workspace_foundation(
    settings: Settings, *, email: str = "owner@example.invalid"
) -> tuple[UUID, UUID, UUID]:
    """Insert a workspace and its deferred owner relationship atomically."""
    user_id, workspace_id, membership_id = uuid4(), uuid4(), uuid4()
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES (:id, :email, 'Schema Owner', 'ACTIVE', 'en', 'UTC')"
                ),
                {"id": user_id, "email": email},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "owner_membership_id, owner_role, owner_membership_status, status) "
                    "VALUES (:id, 'Schema Workspace', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    ":membership_id, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {"id": workspace_id, "membership_id": membership_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) "
                    "VALUES (:id, :workspace_id, :user_id, 'ADMIN', 'ACTIVE')"
                ),
                {"id": membership_id, "workspace_id": workspace_id, "user_id": user_id},
            )
    finally:
        await engine.dispose()
    return user_id, workspace_id, membership_id


@pytest.mark.postgres
def test_schema_rejects_a_second_active_admin(migrated_database: Settings) -> None:
    """A workspace cannot gain a second Active Admin membership."""

    async def exercise() -> None:
        _, workspace_id, _ = await insert_workspace_foundation(migrated_database)
        engine = create_database_engine(migrated_database)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    second_user = uuid4()
                    await connection.execute(
                        text(
                            "INSERT INTO user_accounts "
                            "(id, normalized_email, display_name, status, "
                            "preferred_language, timezone) "
                            "VALUES (:id, 'second@example.invalid', 'Second', "
                            "'ACTIVE', 'en', 'UTC')"
                        ),
                        {"id": second_user},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO workspace_memberships "
                            "(id, workspace_id, user_account_id, role, status) "
                            "VALUES (:id, :workspace_id, :user_id, 'ADMIN', 'ACTIVE')"
                        ),
                        {
                            "id": uuid4(),
                            "workspace_id": workspace_id,
                            "user_id": second_user,
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_schema_rejects_a_cross_workspace_owner(migrated_database: Settings) -> None:
    """An Active Admin membership can own only its own workspace."""

    async def exercise() -> None:
        _, first_workspace_id, _ = await insert_workspace_foundation(
            migrated_database, email="first-owner@example.invalid"
        )
        _, _, second_membership_id = await insert_workspace_foundation(
            migrated_database, email="other-owner@example.invalid"
        )
        engine = create_database_engine(migrated_database)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "UPDATE workspaces SET owner_membership_id = :membership_id "
                            "WHERE id = :workspace_id"
                        ),
                        {
                            "membership_id": second_membership_id,
                            "workspace_id": first_workspace_id,
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
@pytest.mark.parametrize("module_code", ["lowercase", "HAS-DASH"])
def test_schema_rejects_invalid_module_codes(migrated_database: Settings, module_code: str) -> None:
    """Module codes must use the bounded uppercase registry format."""

    async def exercise() -> None:
        _, workspace_id, _ = await insert_workspace_foundation(
            migrated_database, email=f"{module_code.lower()}@example.invalid"
        )
        engine = create_database_engine(migrated_database)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO workspace_modules "
                            "(id, workspace_id, module_code, enabled) "
                            "VALUES (:id, :workspace_id, :module_code, true)"
                        ),
                        {
                            "id": uuid4(),
                            "workspace_id": workspace_id,
                            "module_code": module_code,
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_schema_rejects_duplicate_modules(migrated_database: Settings) -> None:
    """A workspace can have only one configuration row for each module."""

    async def exercise() -> None:
        _, workspace_id, _ = await insert_workspace_foundation(
            migrated_database, email="module-owner@example.invalid"
        )
        engine = create_database_engine(migrated_database)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO workspace_modules "
                            "(id, workspace_id, module_code, enabled) "
                            "VALUES (:id, :workspace_id, 'HOUSEHOLD_FINANCE', true)"
                        ),
                        {"id": uuid4(), "workspace_id": workspace_id},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO workspace_modules "
                            "(id, workspace_id, module_code, enabled) "
                            "VALUES (:id, :workspace_id, 'HOUSEHOLD_FINANCE', false)"
                        ),
                        {"id": uuid4(), "workspace_id": workspace_id},
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())
