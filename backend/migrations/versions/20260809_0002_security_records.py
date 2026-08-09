"""Add digest-only security lifecycle and append-only audit records.

Revision ID: 20260809_0002
Revises: 20260809_0001

Owner: Identity, Workspace Access, and Audit modules
Issue: #44
Compatibility: PostgreSQL 18; forward migration from the Phase 1 foundation
Validation: clean/incremental migration, constraint, index, and prohibited-column tests
Rollback: removes only the five Issue #44 tables and one supporting membership constraint
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0002"
down_revision: str | None = "20260809_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def mutable_columns() -> list[sa.Column[object] | sa.CheckConstraint]:
    """Return shared mutation audit and optimistic-lock columns."""
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


def digest_algorithm_constraint() -> sa.CheckConstraint:
    """Keep digest representation versioned and purpose-specific."""
    return sa.CheckConstraint("digest_algorithm_code = 'SHA256'", name="valid_digest_algorithm")


def upgrade() -> None:
    """Create the Phase 1 security-sensitive persistence records."""
    op.create_unique_constraint(
        "uq_membership_activation_reference",
        "workspace_memberships",
        ["workspace_id", "id", "user_account_id"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rotated_from_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("access_credential_digest", sa.String(length=128), nullable=False),
        sa.Column("refresh_credential_digest", sa.String(length=128), nullable=False),
        sa.Column("csrf_credential_digest", sa.String(length=128), nullable=False),
        sa.Column(
            "digest_algorithm_code",
            sa.String(length=16),
            server_default="SHA256",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason_code", sa.String(length=64), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
        *mutable_columns(),
        digest_algorithm_constraint(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED', 'REUSE_DETECTED')",
            name="valid_status",
        ),
        sa.CheckConstraint("access_expires_at > issued_at", name="access_expiry_after_issue"),
        sa.CheckConstraint("refresh_idle_expires_at > issued_at", name="idle_expiry_after_issue"),
        sa.CheckConstraint("absolute_expires_at > issued_at", name="absolute_expiry_after_issue"),
        sa.CheckConstraint(
            "access_expires_at <= absolute_expires_at", name="access_within_absolute_expiry"
        ),
        sa.CheckConstraint(
            "refresh_idle_expires_at <= absolute_expires_at", name="idle_within_absolute_expiry"
        ),
        sa.CheckConstraint(
            "(status IN ('ROTATED', 'REUSE_DETECTED')) = (last_rotated_at IS NOT NULL)",
            name="rotation_evidence",
        ),
        sa.CheckConstraint(
            "(status IN ('REVOKED', 'REUSE_DETECTED')) = "
            "(revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        sa.CheckConstraint(
            "(status = 'REUSE_DETECTED') = (reuse_detected_at IS NOT NULL)",
            name="reuse_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_session_id"],
            ["auth_sessions.id"],
            name="fk_session_rotated_from_session",
        ),
        sa.ForeignKeyConstraint(
            ["user_account_id"], ["user_accounts.id"], name="fk_session_user_account"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint(
            "access_credential_digest", name="uq_auth_sessions_access_credential_digest"
        ),
        sa.UniqueConstraint(
            "refresh_credential_digest", name="uq_auth_sessions_refresh_credential_digest"
        ),
        sa.UniqueConstraint(
            "csrf_credential_digest", name="uq_auth_sessions_csrf_credential_digest"
        ),
        sa.UniqueConstraint("rotated_from_session_id", name="uq_session_single_rotation_child"),
    )
    op.create_index("ix_session_account_status", "auth_sessions", ["user_account_id", "status"])
    op.create_index("ix_session_family_status", "auth_sessions", ["family_id", "status"])
    op.create_index(
        "ix_session_account_absolute_expiry",
        "auth_sessions",
        ["user_account_id", "absolute_expires_at"],
    )
    op.create_index("ix_session_idle_expiry", "auth_sessions", ["refresh_idle_expires_at"])

    op.create_table(
        "activation_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_digest", sa.String(length=128), nullable=False),
        sa.Column(
            "digest_algorithm_code",
            sa.String(length=16),
            server_default="SHA256",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason_code", sa.String(length=64), nullable=True),
        *mutable_columns(),
        digest_algorithm_constraint(),
        sa.CheckConstraint(
            "status IN ('ISSUED', 'USED', 'REVOKED', 'EXPIRED')", name="valid_status"
        ),
        sa.CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
        sa.CheckConstraint("(status = 'USED') = (used_at IS NOT NULL)", name="use_evidence"),
        sa.CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "membership_id", "user_account_id"],
            [
                "workspace_memberships.workspace_id",
                "workspace_memberships.id",
                "workspace_memberships.user_account_id",
            ],
            name="fk_activation_membership_identity",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activation_challenges"),
        sa.UniqueConstraint("challenge_digest", name="uq_activation_challenges_challenge_digest"),
    )
    op.create_index(
        "ix_activation_membership_status",
        "activation_challenges",
        ["workspace_id", "membership_id", "status"],
    )
    op.create_index(
        "ix_activation_account_expiry",
        "activation_challenges",
        ["user_account_id", "expires_at"],
    )

    op.create_table(
        "recovery_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("challenge_digest", sa.String(length=128), nullable=False),
        sa.Column(
            "digest_algorithm_code",
            sa.String(length=16),
            server_default="SHA256",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason_code", sa.String(length=64), nullable=True),
        *mutable_columns(),
        digest_algorithm_constraint(),
        sa.CheckConstraint(
            "status IN ('ISSUED', 'USED', 'REVOKED', 'EXPIRED')", name="valid_status"
        ),
        sa.CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
        sa.CheckConstraint("(status = 'USED') = (used_at IS NOT NULL)", name="use_evidence"),
        sa.CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="nonnegative_attempt_count"),
        sa.ForeignKeyConstraint(
            ["user_account_id"], ["user_accounts.id"], name="fk_recovery_user_account"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_challenges"),
        sa.UniqueConstraint("challenge_digest", name="uq_recovery_challenges_challenge_digest"),
    )
    op.create_index(
        "ix_recovery_account_status", "recovery_challenges", ["user_account_id", "status"]
    )
    op.create_index(
        "ix_recovery_account_expiry", "recovery_challenges", ["user_account_id", "expires_at"]
    )

    op.create_table(
        "ownership_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_owner_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_confirmation_digest", sa.String(length=128), nullable=False),
        sa.Column(
            "digest_algorithm_code",
            sa.String(length=16),
            server_default="SHA256",
            nullable=False,
        ),
        sa.Column("former_owner_role_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "initiated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        *mutable_columns(),
        digest_algorithm_constraint(),
        sa.CheckConstraint(
            "status IN ('INITIATED', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'COMPLETED')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "former_owner_role_code IN ('CONTRIBUTOR', 'ADVISOR')",
            name="valid_former_owner_role",
        ),
        sa.CheckConstraint(
            "current_owner_membership_id <> target_membership_id",
            name="distinct_transfer_memberships",
        ),
        sa.CheckConstraint("expires_at > initiated_at", name="expiry_after_initiation"),
        sa.CheckConstraint(
            "(status IN ('CONFIRMED', 'COMPLETED')) = (confirmed_at IS NOT NULL)",
            name="confirmation_evidence",
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED') = (cancelled_at IS NOT NULL AND reason_code IS NOT NULL)",
            name="cancellation_evidence",
        ),
        sa.CheckConstraint(
            "(status = 'EXPIRED') = (expired_at IS NOT NULL)", name="expiry_evidence"
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED') = (completed_at IS NOT NULL)", name="completion_evidence"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "current_owner_membership_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.id"],
            name="fk_transfer_current_owner_membership",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "target_membership_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.id"],
            name="fk_transfer_target_membership",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_transfer_workspace"),
        sa.PrimaryKeyConstraint("id", name="pk_ownership_transfers"),
        sa.UniqueConstraint(
            "target_confirmation_digest",
            name="uq_ownership_transfers_target_confirmation_digest",
        ),
    )
    op.create_index(
        "ix_transfer_workspace_status", "ownership_transfers", ["workspace_id", "status"]
    )
    op.create_index(
        "ix_transfer_target_status", "ownership_transfers", ["target_membership_id", "status"]
    )
    op.create_index("ix_transfer_expiry", "ownership_transfers", ["expires_at", "status"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_code", sa.String(length=16), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type_code", sa.String(length=16), nullable=False),
        sa.Column("actor_user_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_code", sa.String(length=64), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("resource_type_code", sa.String(length=64), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_code", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("source_code", sa.String(length=64), nullable=True),
        sa.Column("context_code", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("scope_code IN ('GLOBAL', 'WORKSPACE')", name="valid_scope"),
        sa.CheckConstraint(
            "(scope_code = 'GLOBAL' AND workspace_id IS NULL) OR "
            "(scope_code = 'WORKSPACE' AND workspace_id IS NOT NULL)",
            name="scope_workspace_consistency",
        ),
        sa.CheckConstraint("actor_type_code IN ('SYSTEM', 'USER')", name="valid_actor_type"),
        sa.CheckConstraint(
            "(actor_type_code = 'SYSTEM' AND actor_user_account_id IS NULL "
            "AND actor_membership_id IS NULL) OR "
            "(actor_type_code = 'USER' AND actor_user_account_id IS NOT NULL)",
            name="actor_identity_consistency",
        ),
        sa.CheckConstraint(
            "actor_membership_id IS NULL OR workspace_id IS NOT NULL",
            name="membership_requires_workspace",
        ),
        sa.CheckConstraint("action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="valid_action_code"),
        sa.CheckConstraint("module_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="valid_module_code"),
        sa.CheckConstraint("result_code IN ('SUCCEEDED', 'FAILED', 'DENIED')", name="valid_result"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "actor_membership_id", "actor_user_account_id"],
            [
                "workspace_memberships.workspace_id",
                "workspace_memberships.id",
                "workspace_memberships.user_account_id",
            ],
            name="fk_audit_actor_membership_identity",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_account_id"],
            ["user_accounts.id"],
            name="fk_audit_actor_user_account",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_audit_workspace"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_workspace_occurred", "audit_events", ["workspace_id", "occurred_at", "id"]
    )
    op.create_index("ix_audit_action_occurred", "audit_events", ["action_code", "occurred_at"])
    op.create_index(
        "ix_audit_actor_occurred", "audit_events", ["actor_user_account_id", "occurred_at"]
    )
    op.create_index(
        "ix_audit_resource",
        "audit_events",
        ["resource_type_code", "resource_id", "occurred_at"],
    )
    op.create_index("ix_audit_correlation", "audit_events", ["correlation_id"])


def downgrade() -> None:
    """Remove Issue #44 records in reverse dependency order."""
    op.drop_index("ix_audit_correlation", table_name="audit_events")
    op.drop_index("ix_audit_resource", table_name="audit_events")
    op.drop_index("ix_audit_actor_occurred", table_name="audit_events")
    op.drop_index("ix_audit_action_occurred", table_name="audit_events")
    op.drop_index("ix_audit_workspace_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_transfer_expiry", table_name="ownership_transfers")
    op.drop_index("ix_transfer_target_status", table_name="ownership_transfers")
    op.drop_index("ix_transfer_workspace_status", table_name="ownership_transfers")
    op.drop_table("ownership_transfers")
    op.drop_index("ix_recovery_account_expiry", table_name="recovery_challenges")
    op.drop_index("ix_recovery_account_status", table_name="recovery_challenges")
    op.drop_table("recovery_challenges")
    op.drop_index("ix_activation_account_expiry", table_name="activation_challenges")
    op.drop_index("ix_activation_membership_status", table_name="activation_challenges")
    op.drop_table("activation_challenges")
    op.drop_index("ix_session_idle_expiry", table_name="auth_sessions")
    op.drop_index("ix_session_account_absolute_expiry", table_name="auth_sessions")
    op.drop_index("ix_session_family_status", table_name="auth_sessions")
    op.drop_index("ix_session_account_status", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint(
        "uq_membership_activation_reference", "workspace_memberships", type_="unique"
    )
