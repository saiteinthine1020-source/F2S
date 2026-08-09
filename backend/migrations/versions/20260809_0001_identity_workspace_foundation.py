"""Create the Identity and Workspace Access schema foundation.

Revision ID: 20260809_0001
Revises: None

Owner: Identity and Workspace Access modules
Issue: #43
Compatibility: PostgreSQL 18; additive first migration
Validation: upgrade/downgrade and constraint integration tests
Rollback: removes only the five empty foundation tables created here
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column[object] | sa.CheckConstraint]:
    """Return the shared audit/version columns for mutable aggregates."""
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("version > 0", name="positive_version"),
    ]


def upgrade() -> None:
    """Create the initial identity and workspace access foundation."""
    op.create_table(
        "bootstrap_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("singleton_key", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("singleton_key = 'INSTALLATION'", name="singleton_installation"),
        sa.PrimaryKeyConstraint("id", name="pk_bootstrap_state"),
        sa.UniqueConstraint("singleton_key", name="uq_bootstrap_state_singleton_key"),
    )
    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_digest", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("preferred_language", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "normalized_email = lower(btrim(normalized_email))",
            name="normalized_email_canonical",
        ),
        sa.CheckConstraint(
            "position('@' in normalized_email) > 1",
            name="normalized_email_shape",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_ACTIVATION', 'ACTIVE', 'SUSPENDED', 'LOCKED', 'CLOSED')",
            name="valid_status",
        ),
        sa.CheckConstraint("char_length(btrim(display_name)) > 0", name="display_name_not_blank"),
        sa.PrimaryKeyConstraint("id", name="pk_user_accounts"),
        sa.UniqueConstraint("normalized_email", name="uq_user_accounts_normalized_email"),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("base_currency_code", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("preferred_language", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("business_category_code", sa.String(length=64), nullable=True),
        sa.Column("farm_type_code", sa.String(length=64), nullable=True),
        sa.Column("owner_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_role", sa.String(length=16), server_default="ADMIN", nullable=False),
        sa.Column(
            "owner_membership_status", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint(
            "type IN ('HOUSEHOLD', 'FARM', 'MICROBUSINESS', 'SMALL_BUSINESS', "
            "'COMBINED', 'CUSTOM')",
            name="valid_type",
        ),
        sa.CheckConstraint("base_currency_code ~ '^[A-Z]{3}$'", name="valid_currency_code"),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')", name="valid_status"),
        sa.CheckConstraint("owner_role = 'ADMIN'", name="owner_role_admin"),
        sa.CheckConstraint("owner_membership_status = 'ACTIVE'", name="owner_status_active"),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'CONTRIBUTOR', 'ADVISOR')",
            name="valid_role",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'REVOKED')",
            name="valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_account_id"], ["user_accounts.id"], name="fk_membership_user_account"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_membership_workspace"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_memberships"),
        sa.UniqueConstraint("workspace_id", "user_account_id", name="uq_membership_workspace_user"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_membership_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "id", "role", "status", name="uq_membership_owner_reference"
        ),
    )
    op.create_index(
        "ix_membership_workspace_status",
        "workspace_memberships",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_membership_user_status", "workspace_memberships", ["user_account_id", "status"]
    )
    op.create_index(
        "uq_membership_one_active_admin",
        "workspace_memberships",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("role = 'ADMIN' AND status = 'ACTIVE'"),
    )
    op.create_foreign_key(
        "fk_workspaces_owner_membership_workspace_memberships",
        "workspaces",
        "workspace_memberships",
        ["id", "owner_membership_id", "owner_role", "owner_membership_status"],
        ["workspace_id", "id", "role", "status"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "workspace_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "module_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="valid_module_code",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_module_workspace"),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_modules"),
        sa.UniqueConstraint("workspace_id", "module_code", name="uq_module_workspace_code"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_module_workspace_id"),
    )
    op.create_index("ix_module_workspace_enabled", "workspace_modules", ["workspace_id", "enabled"])


def downgrade() -> None:
    """Remove the empty foundation in reverse dependency order."""
    op.drop_index("ix_module_workspace_enabled", table_name="workspace_modules")
    op.drop_table("workspace_modules")
    op.drop_constraint(
        "fk_workspaces_owner_membership_workspace_memberships",
        "workspaces",
        type_="foreignkey",
    )
    op.drop_index("uq_membership_one_active_admin", table_name="workspace_memberships")
    op.drop_index("ix_membership_user_status", table_name="workspace_memberships")
    op.drop_index("ix_membership_workspace_status", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("user_accounts")
    op.drop_table("bootstrap_state")
