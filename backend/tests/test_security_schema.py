"""Security lifecycle and audit schema invariant tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.infrastructure.database.session import create_database_engine

SECURITY_TABLES = {
    "auth_sessions",
    "activation_challenges",
    "recovery_challenges",
    "ownership_transfers",
    "audit_events",
}


async def insert_workspace_members(
    settings: Settings, *, email_prefix: str
) -> tuple[UUID, UUID, UUID, UUID]:
    """Insert one owner and one target membership for transfer constraint tests."""
    owner_user_id, target_user_id = uuid4(), uuid4()
    workspace_id, owner_membership_id, target_membership_id = uuid4(), uuid4(), uuid4()
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES (:owner_id, :owner_email, 'Owner', 'ACTIVE', 'en', 'UTC'), "
                    "(:target_id, :target_email, 'Target', 'ACTIVE', 'en', 'UTC')"
                ),
                {
                    "owner_id": owner_user_id,
                    "owner_email": f"{email_prefix}-owner@example.invalid",
                    "target_id": target_user_id,
                    "target_email": f"{email_prefix}-target@example.invalid",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "owner_membership_id, owner_role, owner_membership_status, status) "
                    "VALUES (:id, 'Security Workspace', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    ":owner_membership_id, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {"id": workspace_id, "owner_membership_id": owner_membership_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) VALUES "
                    "(:owner_membership_id, :workspace_id, :owner_user_id, 'ADMIN', 'ACTIVE'), "
                    "(:target_membership_id, :workspace_id, :target_user_id, "
                    "'CONTRIBUTOR', 'ACTIVE')"
                ),
                {
                    "owner_membership_id": owner_membership_id,
                    "workspace_id": workspace_id,
                    "owner_user_id": owner_user_id,
                    "target_membership_id": target_membership_id,
                    "target_user_id": target_user_id,
                },
            )
    finally:
        await engine.dispose()
    return owner_user_id, workspace_id, owner_membership_id, target_membership_id


@pytest.mark.postgres
def test_security_tables_store_only_digest_credentials(migrated_database: Settings) -> None:
    """Secret-bearing concepts have digest columns and no raw bearer-value column."""
    engine = create_engine(migrated_database.database_url.set(drivername="postgresql+psycopg"))
    try:
        inspector = inspect(engine)
        assert SECURITY_TABLES.issubset(set(inspector.get_table_names()))

        for table_name in SECURITY_TABLES:
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            assert "token" not in columns
            assert "secret" not in columns
            assert "credential" not in columns
            assert "challenge" not in columns
            for column_name in columns:
                if any(word in column_name for word in ("credential", "challenge", "confirmation")):
                    assert column_name.endswith("_digest")

        expected_unique_digests = {
            "auth_sessions": {
                "access_credential_digest",
                "refresh_credential_digest",
                "csrf_credential_digest",
            },
            "activation_challenges": {"challenge_digest"},
            "recovery_challenges": {"challenge_digest"},
            "ownership_transfers": {"target_confirmation_digest"},
        }
        for table_name, digest_columns in expected_unique_digests.items():
            unique_columns = {
                column
                for constraint in inspector.get_unique_constraints(table_name)
                for column in constraint["column_names"]
            }
            assert digest_columns <= unique_columns
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_duplicate_recovery_digest_is_rejected(migrated_database: Settings) -> None:
    """A purpose-specific digest cannot identify more than one recovery challenge."""

    async def exercise() -> None:
        engine = create_database_engine(migrated_database)
        user_id = uuid4()
        issued_at = datetime.now(UTC)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO user_accounts "
                            "(id, normalized_email, display_name, status, "
                            "preferred_language, timezone) VALUES "
                            "(:id, 'recovery@example.invalid', 'Recovery', "
                            "'ACTIVE', 'en', 'UTC')"
                        ),
                        {"id": user_id},
                    )
                    for challenge_id in (uuid4(), uuid4()):
                        await connection.execute(
                            text(
                                "INSERT INTO recovery_challenges "
                                "(id, user_account_id, challenge_digest, status, "
                                "issued_at, expires_at) VALUES "
                                "(:id, :user_id, 'duplicate-recovery-digest', 'ISSUED', "
                                ":issued_at, :expires_at)"
                            ),
                            {
                                "id": challenge_id,
                                "user_id": user_id,
                                "issued_at": issued_at,
                                "expires_at": issued_at + timedelta(hours=24),
                            },
                        )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_audit_events_keep_required_identity_references(migrated_database: Settings) -> None:
    """Audit evidence references its workspace, actor account, and actor membership."""
    engine = create_engine(migrated_database.database_url.set(drivername="postgresql+psycopg"))
    try:
        foreign_keys = {
            foreign_key["name"]: foreign_key["referred_table"]
            for foreign_key in inspect(engine).get_foreign_keys("audit_events")
        }
        assert foreign_keys == {
            "fk_audit_actor_membership_identity": "workspace_memberships",
            "fk_audit_actor_user_account": "user_accounts",
            "fk_audit_workspace": "workspaces",
        }
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_cross_workspace_ownership_transfer_is_rejected(migrated_database: Settings) -> None:
    """Both transfer memberships must belong to the protected workspace."""

    async def exercise() -> None:
        _, workspace_id, owner_membership_id, _ = await insert_workspace_members(
            migrated_database, email_prefix="transfer-one"
        )
        _, _, _, foreign_target_membership_id = await insert_workspace_members(
            migrated_database, email_prefix="transfer-two"
        )
        engine = create_database_engine(migrated_database)
        initiated_at = datetime.now(UTC)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO ownership_transfers "
                            "(id, workspace_id, current_owner_membership_id, "
                            "target_membership_id, target_confirmation_digest, "
                            "former_owner_role_code, status, initiated_at, expires_at) "
                            "VALUES (:id, :workspace_id, :owner_id, :target_id, "
                            "'cross-workspace-confirmation-digest', 'CONTRIBUTOR', "
                            "'INITIATED', :initiated_at, :expires_at)"
                        ),
                        {
                            "id": uuid4(),
                            "workspace_id": workspace_id,
                            "owner_id": owner_membership_id,
                            "target_id": foreign_target_membership_id,
                            "initiated_at": initiated_at,
                            "expires_at": initiated_at + timedelta(hours=24),
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.postgres
def test_security_lifecycle_and_timezone_constraints(migrated_database: Settings) -> None:
    """Security lifecycle times are timezone-aware and invalid expiry is rejected."""
    sync_engine = create_engine(migrated_database.database_url.set(drivername="postgresql+psycopg"))
    try:
        inspector = inspect(sync_engine)
        for table_name, column_name in (
            ("auth_sessions", "issued_at"),
            ("activation_challenges", "expires_at"),
            ("recovery_challenges", "expires_at"),
            ("ownership_transfers", "initiated_at"),
            ("audit_events", "occurred_at"),
        ):
            column = next(
                item for item in inspector.get_columns(table_name) if item["name"] == column_name
            )
            assert cast(DateTime, column["type"]).timezone is True
    finally:
        sync_engine.dispose()

    async def reject_invalid_expiry() -> None:
        engine = create_database_engine(migrated_database)
        user_id = uuid4()
        issued_at = datetime.now(UTC)
        try:
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO user_accounts "
                            "(id, normalized_email, display_name, status, "
                            "preferred_language, timezone) VALUES "
                            "(:id, 'expiry@example.invalid', 'Expiry', 'ACTIVE', 'en', 'UTC')"
                        ),
                        {"id": user_id},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO recovery_challenges "
                            "(id, user_account_id, challenge_digest, status, "
                            "issued_at, expires_at) VALUES "
                            "(:id, :user_id, 'invalid-expiry-digest', 'ISSUED', "
                            ":issued_at, :expires_at)"
                        ),
                        {
                            "id": uuid4(),
                            "user_id": user_id,
                            "issued_at": issued_at,
                            "expires_at": issued_at - timedelta(seconds=1),
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(reject_invalid_expiry())


@pytest.mark.postgres
def test_required_security_query_indexes_exist(migrated_database: Settings) -> None:
    """Session-family, expiry, transfer, and audit access paths are explicitly indexed."""
    expected_indexes = {
        "auth_sessions": {
            "ix_session_account_status",
            "ix_session_family_status",
            "ix_session_account_absolute_expiry",
            "ix_session_idle_expiry",
        },
        "activation_challenges": {
            "ix_activation_membership_status",
            "ix_activation_account_expiry",
        },
        "recovery_challenges": {
            "ix_recovery_account_status",
            "ix_recovery_account_expiry",
        },
        "ownership_transfers": {
            "ix_transfer_workspace_status",
            "ix_transfer_target_status",
            "ix_transfer_expiry",
        },
        "audit_events": {
            "ix_audit_workspace_occurred",
            "ix_audit_action_occurred",
            "ix_audit_actor_occurred",
            "ix_audit_resource",
            "ix_audit_correlation",
        },
    }
    engine = create_engine(migrated_database.database_url.set(drivername="postgresql+psycopg"))
    try:
        inspector = inspect(engine)
        for table_name, required_names in expected_indexes.items():
            actual_names = {index["name"] for index in inspector.get_indexes(table_name)}
            assert required_names <= actual_names
    finally:
        engine.dispose()
