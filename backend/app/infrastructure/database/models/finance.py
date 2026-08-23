"""SQLAlchemy mappings for workspace-scoped canonical Household Finance records."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


def _actor_foreign_key(column_name: str, constraint_name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", column_name],
        ["workspace_memberships.workspace_id", "workspace_memberships.id"],
        name=constraint_name,
        ondelete="RESTRICT",
    )


class FinanceCategory(Base):
    """Archivable workspace-owned classification retained by historical events."""

    __tablename__ = "finance_categories"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 128", name="valid_display_name"
        ),
        CheckConstraint(
            "char_length(normalized_name) BETWEEN 1 AND 128 "
            "AND normalized_name = lower(btrim(normalized_name))",
            name="valid_normalized_name",
        ),
        CheckConstraint(
            "applicability_code IN ('INCOME', 'EXPENSE', 'BOTH')", name="valid_applicability"
        ),
        CheckConstraint(
            "activity_classification_code IS NULL OR "
            "activity_classification_code IN ('HOUSEHOLD', 'FARM', 'BUSINESS')",
            name="valid_activity_classification",
        ),
        CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="valid_status"),
        CheckConstraint(
            "(status = 'ACTIVE' AND archived_at IS NULL "
            "AND archived_by_membership_id IS NULL AND archive_reason_code IS NULL) OR "
            "(status = 'ARCHIVED' AND archived_at IS NOT NULL "
            "AND archived_by_membership_id IS NOT NULL AND archive_reason_code IS NOT NULL)",
            name="archive_evidence",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        _actor_foreign_key("created_by_membership_id", "fk_finance_category_creator"),
        _actor_foreign_key("updated_by_membership_id", "fk_finance_category_updater"),
        _actor_foreign_key("archived_by_membership_id", "fk_finance_category_archiver"),
        UniqueConstraint("workspace_id", "id", name="uq_finance_category_workspace_id"),
        Index(
            "uq_finance_category_active_scope_name",
            "workspace_id",
            "normalized_name",
            "applicability_code",
            text("COALESCE(activity_classification_code, '')"),
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_finance_category_workspace_status_name",
            "workspace_id",
            "status",
            "normalized_name",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False)
    applicability_code: Mapped[str] = mapped_column(String(16), nullable=False)
    activity_classification_code: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    updated_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    archived_by_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class FinancialEvent(Base):
    """One exact canonical cash event with approval and posting state kept separate."""

    __tablename__ = "financial_events"
    __table_args__ = (
        CheckConstraint(
            "event_kind IN ('MANUAL_INCOME', 'MANUAL_EXPENSE')", name="valid_event_kind"
        ),
        CheckConstraint("cash_direction IN ('INFLOW', 'OUTFLOW')", name="valid_direction"),
        CheckConstraint(
            "(event_kind = 'MANUAL_INCOME' AND cash_direction = 'INFLOW') OR "
            "(event_kind = 'MANUAL_EXPENSE' AND cash_direction = 'OUTFLOW')",
            name="manual_kind_direction",
        ),
        CheckConstraint(
            "activity_classification_code IN ('HOUSEHOLD', 'FARM', 'BUSINESS')",
            name="valid_activity_classification",
        ),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="valid_currency_code"),
        CheckConstraint(
            "payment_method_code IN "
            "('CASH', 'BANK_TRANSFER', 'MOBILE_MONEY', 'CARD', 'CHEQUE', 'OTHER')",
            name="valid_payment_method",
        ),
        CheckConstraint(
            "counterparty_text IS NULL OR char_length(counterparty_text) BETWEEN 1 AND 256",
            name="valid_counterparty",
        ),
        CheckConstraint(
            "reference_text IS NULL OR char_length(reference_text) BETWEEN 1 AND 128",
            name="valid_reference",
        ),
        CheckConstraint(
            "notes IS NULL OR char_length(notes) BETWEEN 1 AND 2000", name="valid_notes"
        ),
        CheckConstraint(
            "(approval_status = 'PENDING' AND posting_status = 'NOT_EFFECTIVE') OR "
            "(approval_status = 'REJECTED' AND posting_status = 'NOT_EFFECTIVE') OR "
            "(approval_status = 'APPROVED' AND posting_status IN ('EFFECTIVE', 'REVERSED'))",
            name="valid_approval_posting_state",
        ),
        CheckConstraint(
            "(approval_status = 'PENDING' AND reviewed_by_membership_id IS NULL "
            "AND reviewed_at IS NULL AND decision_reason_code IS NULL "
            "AND decision_explanation IS NULL) OR "
            "(approval_status = 'APPROVED' AND reviewed_by_membership_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND decision_reason_code IS NOT NULL "
            "AND decision_explanation IS NULL) OR "
            "(approval_status = 'REJECTED' AND reviewed_by_membership_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND decision_reason_code IS NOT NULL "
            "AND decision_explanation IS NOT NULL)",
            name="decision_evidence",
        ),
        CheckConstraint(
            "reverses_financial_event_id IS NULL OR reverses_financial_event_id <> id",
            name="reversal_not_self",
        ),
        CheckConstraint(
            "replacement_for_financial_event_id IS NULL OR "
            "replacement_for_financial_event_id <> id",
            name="replacement_not_self",
        ),
        CheckConstraint(
            "reverses_financial_event_id IS NULL OR "
            "(approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE')",
            name="reversal_is_effective",
        ),
        CheckConstraint(
            "(archived_at IS NULL AND archived_by_membership_id IS NULL "
            "AND archive_reason_code IS NULL) OR "
            "(archived_at IS NOT NULL AND archived_by_membership_id IS NOT NULL "
            "AND archive_reason_code IS NOT NULL)",
            name="archive_evidence",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        _actor_foreign_key("created_by_membership_id", "fk_financial_event_creator"),
        _actor_foreign_key("updated_by_membership_id", "fk_financial_event_updater"),
        _actor_foreign_key("reviewed_by_membership_id", "fk_financial_event_reviewer"),
        _actor_foreign_key("archived_by_membership_id", "fk_financial_event_archiver"),
        ForeignKeyConstraint(
            ["workspace_id", "finance_category_id"],
            ["finance_categories.workspace_id", "finance_categories.id"],
            name="fk_financial_event_category",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "reverses_financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_reversal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "replacement_for_financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_replacement",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_financial_event_workspace_id"),
        UniqueConstraint("workspace_id", "operation_id", name="uq_financial_event_operation"),
        Index(
            "uq_financial_event_effective_reversal",
            "workspace_id",
            "reverses_financial_event_id",
            unique=True,
            postgresql_where=text(
                "reverses_financial_event_id IS NOT NULL "
                "AND approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE'"
            ),
        ),
        Index(
            "ix_financial_event_workspace_occurred", "workspace_id", text("occurred_on DESC"), "id"
        ),
        Index(
            "ix_financial_event_workspace_state_kind_date",
            "workspace_id",
            "approval_status",
            "posting_status",
            "event_kind",
            "occurred_on",
        ),
        Index(
            "ix_financial_event_category_date",
            "workspace_id",
            "finance_category_id",
            "occurred_on",
        ),
        Index(
            "ix_financial_event_payment_date",
            "workspace_id",
            "payment_method_code",
            "occurred_on",
        ),
        Index(
            "ix_financial_event_reversal_link",
            "workspace_id",
            "reverses_financial_event_id",
        ),
        Index(
            "ix_financial_event_replacement_link",
            "workspace_id",
            "replacement_for_financial_event_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    cash_direction: Mapped[str] = mapped_column(String(8), nullable=False)
    activity_classification_code: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    finance_category_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_method_code: Mapped[str] = mapped_column(String(32), nullable=False)
    counterparty_text: Mapped[str | None] = mapped_column(String(256))
    reference_text: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False)
    posting_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewed_by_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason_code: Mapped[str | None] = mapped_column(String(64))
    decision_explanation: Mapped[str | None] = mapped_column(String(512))
    reverses_financial_event_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    replacement_for_financial_event_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    updated_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    archived_by_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reason_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class FinancialEventReview(Base):
    """Attributed comment or flag sidecar that never mutates a financial fact."""

    __tablename__ = "financial_event_reviews"
    __table_args__ = (
        CheckConstraint("review_kind IN ('COMMENT', 'FLAG')", name="valid_kind"),
        CheckConstraint("char_length(btrim(body_text)) BETWEEN 1 AND 2000", name="valid_body"),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('MISSING_EVIDENCE', 'POSSIBLE_DUPLICATE', 'POSSIBLE_INCORRECT_AMOUNT', "
            "'POSSIBLE_INCORRECT_CATEGORY', 'POSSIBLE_INCORRECT_DATE', 'OTHER')",
            name="valid_reason",
        ),
        CheckConstraint(
            "resolution_code IS NULL OR resolution_code IN "
            "('REVIEWED_NO_CHANGE', 'CORRECTION_REQUIRED', 'DUPLICATE_CONFIRMED', 'OTHER')",
            name="valid_resolution",
        ),
        CheckConstraint(
            "(review_kind = 'COMMENT' AND reason_code IS NULL AND flag_status IS NULL "
            "AND resolved_by_membership_id IS NULL AND resolved_at IS NULL "
            "AND resolution_code IS NULL) OR "
            "(review_kind = 'FLAG' AND reason_code IS NOT NULL AND "
            "((flag_status = 'OPEN' AND resolved_by_membership_id IS NULL "
            "AND resolved_at IS NULL AND resolution_code IS NULL) OR "
            "(flag_status = 'RESOLVED' AND resolved_by_membership_id IS NOT NULL "
            "AND resolved_at IS NOT NULL AND resolution_code IS NOT NULL)))",
            name="valid_lifecycle",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        _actor_foreign_key("created_by_membership_id", "fk_financial_review_creator"),
        _actor_foreign_key("resolved_by_membership_id", "fk_financial_review_resolver"),
        ForeignKeyConstraint(
            ["workspace_id", "financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_review_event",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_financial_review_workspace_id"),
        UniqueConstraint("workspace_id", "operation_id", name="uq_financial_review_operation"),
        Index(
            "ix_financial_review_workspace_event_created",
            "workspace_id",
            "financial_event_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_financial_review_open_flags",
            "workspace_id",
            "financial_event_id",
            "created_at",
            postgresql_where=text("review_kind = 'FLAG' AND flag_status = 'OPEN'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    financial_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    review_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    flag_status: Mapped[str | None] = mapped_column(String(16))
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    resolved_by_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class ProtectedFile(Base):
    """Restricted file metadata; bytes live behind the private storage boundary."""

    __tablename__ = "protected_files"
    __table_args__ = (
        CheckConstraint("purpose_code = 'FINANCIAL_RECEIPT'", name="valid_purpose"),
        CheckConstraint(
            "state IN ('PENDING', 'QUARANTINED', 'AVAILABLE', 'FAILED', 'EXPIRED', 'DELETED')",
            name="valid_state",
        ),
        CheckConstraint(
            "declared_media_type IN ('application/pdf', 'image/jpeg', 'image/png')",
            name="valid_declared_media_type",
        ),
        CheckConstraint(
            "detected_media_type IS NULL OR detected_media_type IN "
            "('application/pdf', 'image/jpeg', 'image/png')",
            name="valid_detected_media_type",
        ),
        CheckConstraint("expected_size BETWEEN 1 AND 10485760", name="valid_expected_size"),
        CheckConstraint(
            "actual_size IS NULL OR actual_size BETWEEN 1 AND 10485760",
            name="valid_actual_size",
        ),
        CheckConstraint("expected_sha256 ~ '^[0-9a-f]{64}$'", name="valid_expected_sha256"),
        CheckConstraint(
            "actual_sha256 IS NULL OR actual_sha256 ~ '^[0-9a-f]{64}$'",
            name="valid_actual_sha256",
        ),
        CheckConstraint("storage_key ~ '^[0-9a-f]{64}$'", name="valid_storage_key"),
        CheckConstraint("char_length(sanitized_filename) BETWEEN 1 AND 128", name="valid_filename"),
        CheckConstraint(
            "(state = 'PENDING' AND uploaded_at IS NULL AND scanned_at IS NULL "
            "AND available_at IS NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'QUARANTINED' AND uploaded_at IS NOT NULL AND scanned_at IS NULL "
            "AND available_at IS NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'AVAILABLE' AND uploaded_at IS NOT NULL AND scanned_at IS NOT NULL "
            "AND available_at IS NOT NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state IN ('FAILED', 'EXPIRED') AND available_at IS NULL "
            "AND deleted_at IS NULL AND failure_code IS NOT NULL) OR "
            "(state = 'DELETED' AND deleted_at IS NOT NULL)",
            name="valid_lifecycle",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        _actor_foreign_key("created_by_membership_id", "fk_protected_file_creator"),
        UniqueConstraint("workspace_id", "id", name="uq_protected_file_workspace_id"),
        UniqueConstraint("workspace_id", "operation_id", name="uq_protected_file_operation"),
        UniqueConstraint("storage_key", name="uq_protected_file_storage_key"),
        Index("ix_protected_file_workspace_state_created", "workspace_id", "state", "created_at"),
        Index(
            "ix_protected_file_cleanup",
            "state",
            "cleanup_after",
            postgresql_where=text("cleanup_after IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purpose_code: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_media_type: Mapped[str | None] = mapped_column(String(64))
    sanitized_filename: Mapped[str] = mapped_column(String(128), nullable=False)
    expected_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actual_size: Mapped[int | None] = mapped_column(BigInteger)
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_sha256: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    reservation_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleanup_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class FinancialEventFile(Base):
    """Append-only receipt association with explicit removal evidence."""

    __tablename__ = "financial_event_files"
    __table_args__ = (
        CheckConstraint("attachment_role = 'RECEIPT'", name="valid_role"),
        CheckConstraint(
            "(removed_at IS NULL AND removed_by_membership_id IS NULL AND removal_reason IS NULL "
            "AND removal_operation_id IS NULL) "
            "OR (removed_at IS NOT NULL AND removed_by_membership_id IS NOT NULL "
            "AND removal_reason IS NOT NULL AND removal_operation_id IS NOT NULL)",
            name="valid_removal",
        ),
        _actor_foreign_key("attached_by_membership_id", "fk_financial_event_file_attacher"),
        _actor_foreign_key("removed_by_membership_id", "fk_financial_event_file_remover"),
        ForeignKeyConstraint(
            ["workspace_id", "financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_file_event",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "protected_file_id"],
            ["protected_files.workspace_id", "protected_files.id"],
            name="fk_financial_event_file_file",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_financial_event_file_workspace_id"),
        Index(
            "uq_financial_event_file_active",
            "workspace_id",
            "financial_event_id",
            "protected_file_id",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
        ),
        Index(
            "ix_financial_event_file_workspace_event_attached",
            "workspace_id",
            "financial_event_id",
            "attached_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    financial_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    protected_file_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    attachment_role: Mapped[str] = mapped_column(String(32), nullable=False)
    attached_by_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    removed_by_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(String(64))
    removal_operation_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
