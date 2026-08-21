"""Workspace-scoped SQLAlchemy repository for Household Finance."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.finance import FinanceCategory, FinancialEvent
from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.workspace_access import (
    Workspace,
    WorkspaceMembership,
    WorkspaceModule,
)
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.household_finance import (
    DuplicateFinanceCategory,
    FinanceCategoryRecord,
    FinanceCategoryStateConflict,
    FinanceCategoryVersionMismatch,
    FinancialEventArchiveScope,
    FinancialEventCursorPosition,
    FinancialEventLifecycleRecord,
    FinancialEventLifecycleStateConflict,
    FinancialEventPage,
    FinancialEventQuery,
    FinancialEventRecord,
    FinancialEventReplacement,
    FinancialEventStateConflict,
    FinancialEventStatusRecord,
    FinancialEventVersionMismatch,
    InvalidFinanceCategory,
    PendingFinancialEventChanges,
)
from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    require_capability,
)


class SqlAlchemyFinanceRepository:
    """Return finance records only through a currently active selected workspace."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_category(
        self, context: AuthorizationContext, *, category_id: UUID
    ) -> FinanceCategoryRecord | None:
        await self._revalidate(context)
        category = await self._session.scalar(
            select(FinanceCategory).where(
                FinanceCategory.workspace_id == context.workspace_id,
                FinanceCategory.id == category_id,
            )
        )
        if category is None:
            return None
        return FinanceCategoryRecord(
            id=category.id,
            display_name=category.display_name,
            applicability_code=category.applicability_code,
            activity_classification_code=category.activity_classification_code,
            status=category.status,
            version=category.version,
        )

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        await self._revalidate(context)
        event = await self._session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
        )
        if event is None:
            return None
        return self._event_record(event)

    async def get_visible_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        await self._revalidate(context)
        statement = select(FinancialEvent).where(
            FinancialEvent.workspace_id == context.workspace_id,
            FinancialEvent.id == event_id,
        )
        if context.role.value == "CONTRIBUTOR":
            statement = statement.where(
                FinancialEvent.created_by_membership_id == context.membership_id
            )
        elif context.role.value == "ADVISOR":
            statement = statement.where(FinancialEvent.approval_status == "APPROVED")
        event = await self._session.scalar(statement)
        return None if event is None else self._event_record(event)

    async def list_visible_events(
        self,
        context: AuthorizationContext,
        *,
        query: FinancialEventQuery,
    ) -> FinancialEventPage:
        await self._revalidate(context)
        statement = select(FinancialEvent).where(
            FinancialEvent.workspace_id == context.workspace_id
        )
        if context.role.value == "CONTRIBUTOR":
            statement = statement.where(
                FinancialEvent.created_by_membership_id == context.membership_id
            )
        elif context.role.value == "ADVISOR":
            statement = statement.where(FinancialEvent.approval_status == "APPROVED")

        if query.archive_scope is FinancialEventArchiveScope.ACTIVE:
            statement = statement.where(FinancialEvent.archived_at.is_(None))
        elif query.archive_scope is FinancialEventArchiveScope.ARCHIVED:
            statement = statement.where(FinancialEvent.archived_at.is_not(None))
        if query.approval_statuses:
            statement = statement.where(FinancialEvent.approval_status.in_(query.approval_statuses))
        if query.occurred_from is not None:
            statement = statement.where(FinancialEvent.occurred_on >= query.occurred_from)
        if query.occurred_to is not None:
            statement = statement.where(FinancialEvent.occurred_on < query.occurred_to)
        if query.category_ids:
            statement = statement.where(FinancialEvent.finance_category_id.in_(query.category_ids))
        if query.event_kinds:
            statement = statement.where(FinancialEvent.event_kind.in_(query.event_kinds))
        if query.cash_directions:
            statement = statement.where(FinancialEvent.cash_direction.in_(query.cash_directions))
        if query.activity_classifications:
            statement = statement.where(
                FinancialEvent.activity_classification_code.in_(query.activity_classifications)
            )
        if query.payment_methods:
            statement = statement.where(
                FinancialEvent.payment_method_code.in_(query.payment_methods)
            )
        if query.currencies:
            statement = statement.where(FinancialEvent.currency_code.in_(query.currencies))
        if query.after is not None:
            position = query.after
            statement = statement.where(
                or_(
                    FinancialEvent.occurred_on < position.occurred_on,
                    and_(
                        FinancialEvent.occurred_on == position.occurred_on,
                        FinancialEvent.created_at < position.created_at,
                    ),
                    and_(
                        FinancialEvent.occurred_on == position.occurred_on,
                        FinancialEvent.created_at == position.created_at,
                        FinancialEvent.id > position.event_id,
                    ),
                )
            )

        rows = (
            await self._session.scalars(
                statement.order_by(
                    FinancialEvent.occurred_on.desc(),
                    FinancialEvent.created_at.desc(),
                    FinancialEvent.id.asc(),
                ).limit(query.page_size + 1)
            )
        ).all()
        has_more = len(rows) > query.page_size
        visible_rows = rows[: query.page_size]
        records = tuple(self._event_record(event) for event in visible_rows)
        next_position = None
        if has_more:
            last = visible_rows[-1]
            next_position = FinancialEventCursorPosition(
                occurred_on=last.occurred_on,
                created_at=last.created_at,
                event_id=last.id,
            )
        return FinancialEventPage(records=records, next_position=next_position)

    async def list_event_status_history(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventStatusRecord, ...] | None:
        visible = await self.get_visible_event(context, event_id=event_id)
        if visible is None:
            return None
        status_by_action = {
            "FINANCIAL_EVENT_SUBMITTED": "PENDING",
            "FINANCIAL_EVENT_PENDING_UPDATED": "PENDING",
            "FINANCIAL_EVENT_CREATED_APPROVED": "APPROVED",
            "FINANCIAL_EVENT_APPROVED": "APPROVED",
            "FINANCIAL_EVENT_REJECTED": "REJECTED",
        }
        rows = (
            await self._session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.workspace_id == context.workspace_id,
                    AuditEvent.resource_type_code == "FINANCIAL_EVENT",
                    AuditEvent.resource_id == event_id,
                    AuditEvent.action_code.in_(tuple(status_by_action)),
                    AuditEvent.result_code == "SUCCEEDED",
                )
                .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
            )
        ).all()
        return tuple(
            FinancialEventStatusRecord(
                action_code=row.action_code,
                approval_status=status_by_action[row.action_code],
                actor_membership_id=row.actor_membership_id,
                occurred_at=row.occurred_at,
            )
            for row in rows
        )

    async def list_categories(
        self, context: AuthorizationContext, *, include_archived: bool
    ) -> tuple[FinanceCategoryRecord, ...]:
        await self._revalidate(context)
        statement = select(FinanceCategory).where(
            FinanceCategory.workspace_id == context.workspace_id
        )
        if not include_archived:
            statement = statement.where(FinanceCategory.status == "ACTIVE")
        categories = (
            await self._session.scalars(
                statement.order_by(FinanceCategory.normalized_name, FinanceCategory.id)
            )
        ).all()
        return tuple(self._category_record(category) for category in categories)

    async def create_category(
        self,
        context: AuthorizationContext,
        *,
        display_name: str,
        normalized_name: str,
        applicability_code: str,
        activity_classification_code: str | None,
    ) -> FinanceCategoryRecord:
        await self._revalidate(context)
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        category = FinanceCategory(
            workspace_id=context.workspace_id,
            display_name=display_name,
            normalized_name=normalized_name,
            applicability_code=applicability_code,
            activity_classification_code=activity_classification_code,
            status="ACTIVE",
            created_by_membership_id=context.membership_id,
            updated_by_membership_id=context.membership_id,
            version=1,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(category)
                await self._session.flush()
        except IntegrityError as error:
            raise DuplicateFinanceCategory from error
        await self._audit(context, AuditAction.FINANCE_CATEGORY_CREATED, category.id)
        return self._category_record(category)

    async def rename_category(
        self,
        context: AuthorizationContext,
        *,
        category_id: UUID,
        expected_version: int,
        display_name: str,
        normalized_name: str,
    ) -> FinanceCategoryRecord:
        category = await self._locked_category(context, category_id)
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        await self._require_mutable_version(context, category, expected_version)
        category.display_name = display_name
        category.normalized_name = normalized_name
        category.updated_by_membership_id = context.membership_id
        category.updated_at = datetime.now(UTC)
        category.version += 1
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as error:
            raise DuplicateFinanceCategory from error
        await self._audit(context, AuditAction.FINANCE_CATEGORY_UPDATED, category.id)
        return self._category_record(category)

    async def archive_category(
        self, context: AuthorizationContext, *, category_id: UUID, expected_version: int
    ) -> FinanceCategoryRecord:
        category = await self._locked_category(context, category_id)
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        await self._require_mutable_version(context, category, expected_version)
        now = datetime.now(UTC)
        category.status = "ARCHIVED"
        category.archived_at = now
        category.archived_by_membership_id = context.membership_id
        category.archive_reason_code = "ADMIN_ARCHIVED"
        category.updated_by_membership_id = context.membership_id
        category.updated_at = now
        category.version += 1
        await self._session.flush()
        await self._audit(context, AuditAction.FINANCE_CATEGORY_ARCHIVED, category.id)
        return self._category_record(category)

    async def create_event(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        event_kind: str,
        cash_direction: str,
        activity_classification_code: str,
        occurred_on: date,
        finance_category_id: UUID,
        amount: Decimal,
        currency_code: str,
        payment_method_code: str,
        counterparty_text: str | None,
        reference_text: str | None,
        notes: str | None,
    ) -> FinancialEventRecord:
        await self._revalidate(context)
        require_capability(context, Capability.CREATE_FINANCIAL_SUBMISSION)
        await self.validate_event_category(
            context,
            category_id=finance_category_id,
            event_kind=event_kind,
            activity_classification_code=activity_classification_code,
        )

        now = datetime.now(UTC)
        is_admin = context.role.value == "ADMIN"
        event = FinancialEvent(
            workspace_id=context.workspace_id,
            event_kind=event_kind,
            cash_direction=cash_direction,
            activity_classification_code=activity_classification_code,
            occurred_on=occurred_on,
            finance_category_id=finance_category_id,
            amount=amount,
            currency_code=currency_code,
            payment_method_code=payment_method_code,
            counterparty_text=counterparty_text,
            reference_text=reference_text,
            notes=notes,
            approval_status="APPROVED" if is_admin else "PENDING",
            posting_status="EFFECTIVE" if is_admin else "NOT_EFFECTIVE",
            reviewed_by_membership_id=context.membership_id if is_admin else None,
            reviewed_at=now if is_admin else None,
            decision_reason_code="ADMIN_CREATED" if is_admin else None,
            operation_id=operation_id,
            created_by_membership_id=context.membership_id,
            updated_by_membership_id=context.membership_id,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self._session.add(event)
        await self._session.flush()
        await self._audit(
            context,
            (
                AuditAction.FINANCIAL_EVENT_CREATED_APPROVED
                if is_admin
                else AuditAction.FINANCIAL_EVENT_SUBMITTED
            ),
            event.id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
        )
        return self._event_record(event)

    async def update_pending_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        changes: PendingFinancialEventChanges,
    ) -> FinancialEventRecord:
        await self._revalidate(context)
        if context.role.value != "CONTRIBUTOR":
            await self._audit_denial(
                context,
                AuditReason.PERMISSION_DENIED,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, Capability.EDIT_OWN_PENDING_SUBMISSION)
        event = await self._session.scalar(
            select(FinancialEvent)
            .where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
                FinancialEvent.created_by_membership_id == context.membership_id,
            )
            .with_for_update()
        )
        if event is None:
            await self._audit_denial(
                context,
                AuditReason.RESOURCE_NOT_FOUND,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if event.version != expected_version:
            await self._audit_denial(
                context,
                AuditReason.STALE_VERSION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventVersionMismatch
        if (
            event.approval_status != "PENDING"
            or event.posting_status != "NOT_EFFECTIVE"
            or event.archived_at is not None
        ):
            await self._audit_denial(
                context,
                AuditReason.INVALID_STATE_TRANSITION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventStateConflict

        activity = (
            changes.activity_classification_code
            if "activity_classification" in changes.changed_fields
            else event.activity_classification_code
        )
        category_id = (
            changes.finance_category_id
            if "finance_category_id" in changes.changed_fields
            else event.finance_category_id
        )
        if activity is None or category_id is None:
            raise ValueError("INVALID_PENDING_EVENT_UPDATE")
        category = await self._session.scalar(
            select(FinanceCategory)
            .where(
                FinanceCategory.workspace_id == context.workspace_id,
                FinanceCategory.id == category_id,
                FinanceCategory.status == "ACTIVE",
            )
            .with_for_update()
        )
        if category is None:
            await self._audit_denial(
                context,
                AuditReason.RESOURCE_NOT_FOUND,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        expected_applicability = "INCOME" if event.event_kind == "MANUAL_INCOME" else "EXPENSE"
        if category.applicability_code not in (expected_applicability, "BOTH") or (
            category.activity_classification_code is not None
            and category.activity_classification_code != activity
        ):
            raise InvalidFinanceCategory

        if "activity_classification" in changes.changed_fields:
            event.activity_classification_code = activity
        if "occurred_on" in changes.changed_fields:
            if changes.occurred_on is None:
                raise ValueError("INVALID_PENDING_EVENT_UPDATE")
            event.occurred_on = changes.occurred_on
        if "finance_category_id" in changes.changed_fields:
            event.finance_category_id = category_id
        if "money" in changes.changed_fields:
            if changes.amount is None or changes.currency_code is None:
                raise ValueError("INVALID_PENDING_EVENT_UPDATE")
            event.amount = changes.amount
            event.currency_code = changes.currency_code
        if "payment_method" in changes.changed_fields:
            if changes.payment_method_code is None:
                raise ValueError("INVALID_PENDING_EVENT_UPDATE")
            event.payment_method_code = changes.payment_method_code
        if "counterparty" in changes.changed_fields:
            event.counterparty_text = changes.counterparty_text
        if "reference" in changes.changed_fields:
            event.reference_text = changes.reference_text
        if "notes" in changes.changed_fields:
            event.notes = changes.notes

        event.updated_by_membership_id = context.membership_id
        event.updated_at = datetime.now(UTC)
        event.version += 1
        await self._session.flush()
        await self._audit(
            context,
            AuditAction.FINANCIAL_EVENT_PENDING_UPDATED,
            event.id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
        )
        return self._event_record(event)

    async def decide_pending_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        approval_status: str,
        posting_status: str,
        reason_code: str,
        explanation: str | None,
    ) -> FinancialEventRecord:
        await self._revalidate(context)
        if context.role.value != "ADMIN":
            await self._audit_denial(
                context,
                AuditReason.PERMISSION_DENIED,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, Capability.APPROVE_OR_REJECT_SUBMISSIONS)
        if (approval_status, posting_status) not in {
            ("APPROVED", "EFFECTIVE"),
            ("REJECTED", "NOT_EFFECTIVE"),
        }:
            raise ValueError("INVALID_FINANCIAL_EVENT_DECISION")
        if (approval_status == "APPROVED") != (explanation is None):
            raise ValueError("INVALID_FINANCIAL_EVENT_DECISION_EVIDENCE")

        event = await self._session.scalar(
            select(FinancialEvent)
            .where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
            .with_for_update()
        )
        if event is None:
            await self._audit_denial(
                context,
                AuditReason.RESOURCE_NOT_FOUND,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if (
            event.approval_status != "PENDING"
            or event.posting_status != "NOT_EFFECTIVE"
            or event.archived_at is not None
        ):
            await self._audit_denial(
                context,
                AuditReason.INVALID_STATE_TRANSITION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventStateConflict

        now = datetime.now(UTC)
        event.approval_status = approval_status
        event.posting_status = posting_status
        event.reviewed_by_membership_id = context.membership_id
        event.reviewed_at = now
        event.decision_reason_code = reason_code
        event.decision_explanation = explanation
        event.updated_by_membership_id = context.membership_id
        event.updated_at = now
        event.version += 1
        await self._session.flush()
        await self._audit(
            context,
            (
                AuditAction.FINANCIAL_EVENT_APPROVED
                if approval_status == "APPROVED"
                else AuditAction.FINANCIAL_EVENT_REJECTED
            ),
            event.id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
        )
        return self._event_record(event)

    async def reverse_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        operation_id: UUID,
        occurred_on: date,
        reason_code: str,
        correction: bool,
        replacement: FinancialEventReplacement | None,
    ) -> FinancialEventLifecycleRecord:
        await self._revalidate(context)
        if context.role.value != "ADMIN":
            await self._audit_denial(
                context,
                AuditReason.PERMISSION_DENIED,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, Capability.APPROVE_OR_REJECT_SUBMISSIONS)
        original = await self._session.scalar(
            select(FinancialEvent)
            .where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
            .with_for_update()
        )
        if original is None:
            await self._audit_denial(
                context,
                AuditReason.RESOURCE_NOT_FOUND,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if original.version != expected_version:
            await self._audit_denial(
                context,
                AuditReason.STALE_VERSION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventVersionMismatch
        if (
            original.approval_status != "APPROVED"
            or original.posting_status != "EFFECTIVE"
            or original.reverses_financial_event_id is not None
        ):
            await self._audit_denial(
                context,
                AuditReason.INVALID_STATE_TRANSITION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventLifecycleStateConflict

        now = datetime.now(UTC)
        reversal = FinancialEvent(
            workspace_id=context.workspace_id,
            event_kind=(
                "MANUAL_EXPENSE" if original.cash_direction == "INFLOW" else "MANUAL_INCOME"
            ),
            cash_direction="OUTFLOW" if original.cash_direction == "INFLOW" else "INFLOW",
            activity_classification_code=original.activity_classification_code,
            occurred_on=occurred_on,
            finance_category_id=original.finance_category_id,
            amount=original.amount,
            currency_code=original.currency_code,
            payment_method_code=original.payment_method_code,
            counterparty_text=original.counterparty_text,
            reference_text=original.reference_text,
            notes=original.notes,
            approval_status="APPROVED",
            posting_status="EFFECTIVE",
            reviewed_by_membership_id=context.membership_id,
            reviewed_at=now,
            decision_reason_code=reason_code,
            reverses_financial_event_id=original.id,
            operation_id=operation_id,
            created_by_membership_id=context.membership_id,
            updated_by_membership_id=context.membership_id,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self._session.add(reversal)
        replacement_event: FinancialEvent | None = None
        if replacement is not None:
            replacement_event = FinancialEvent(
                workspace_id=context.workspace_id,
                event_kind=replacement.event_kind,
                cash_direction=replacement.cash_direction,
                activity_classification_code=replacement.activity_classification_code,
                occurred_on=replacement.occurred_on,
                finance_category_id=replacement.finance_category_id,
                amount=replacement.amount,
                currency_code=replacement.currency_code,
                payment_method_code=replacement.payment_method_code,
                counterparty_text=replacement.counterparty_text,
                reference_text=replacement.reference_text,
                notes=replacement.notes,
                approval_status="APPROVED",
                posting_status="EFFECTIVE",
                reviewed_by_membership_id=context.membership_id,
                reviewed_at=now,
                decision_reason_code="CORRECTION_REPLACEMENT",
                replacement_for_financial_event_id=original.id,
                operation_id=uuid5(operation_id, "replacement"),
                created_by_membership_id=context.membership_id,
                updated_by_membership_id=context.membership_id,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self._session.add(replacement_event)

        # The database guard validates a new reversal against the original's
        # still-effective state. Both writes remain in this transaction, but
        # their flush order is part of the canonical transition contract.
        await self._session.flush()
        original.posting_status = "REVERSED"
        original.updated_by_membership_id = context.membership_id
        original.updated_at = now
        original.version += 1
        await self._session.flush()
        await self._audit(
            context,
            (
                AuditAction.FINANCIAL_EVENT_CORRECTED
                if correction
                else AuditAction.FINANCIAL_EVENT_REVERSED
            ),
            original.id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
        )
        return FinancialEventLifecycleRecord(
            original=self._event_record(original),
            reversal=self._event_record(reversal),
            replacement=(
                self._event_record(replacement_event) if replacement_event is not None else None
            ),
        )

    async def archive_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        reason_code: str,
    ) -> FinancialEventRecord:
        await self._revalidate(context)
        if context.role.value != "ADMIN":
            await self._audit_denial(
                context,
                AuditReason.PERMISSION_DENIED,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, Capability.APPROVE_OR_REJECT_SUBMISSIONS)
        event = await self._session.scalar(
            select(FinancialEvent)
            .where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
            .with_for_update()
        )
        if event is None:
            await self._audit_denial(
                context,
                AuditReason.RESOURCE_NOT_FOUND,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if event.version != expected_version:
            await self._audit_denial(
                context,
                AuditReason.STALE_VERSION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventVersionMismatch
        if event.approval_status == "PENDING" or event.archived_at is not None:
            await self._audit_denial(
                context,
                AuditReason.INVALID_STATE_TRANSITION,
                resource_type=AuditResourceType.FINANCIAL_EVENT,
            )
            raise FinancialEventLifecycleStateConflict
        now = datetime.now(UTC)
        event.archived_at = now
        event.archived_by_membership_id = context.membership_id
        event.archive_reason_code = reason_code
        event.updated_by_membership_id = context.membership_id
        event.updated_at = now
        event.version += 1
        await self._session.flush()
        await self._audit(
            context,
            AuditAction.FINANCIAL_EVENT_ARCHIVED,
            event.id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
        )
        return self._event_record(event)

    async def get_lifecycle_result(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventLifecycleRecord | None:
        await self._revalidate(context)
        original = await self._session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.id == event_id,
            )
        )
        if original is None:
            return None
        reversal = await self._session.scalar(
            select(FinancialEvent).where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.reverses_financial_event_id == event_id,
                FinancialEvent.approval_status == "APPROVED",
                FinancialEvent.posting_status == "EFFECTIVE",
            )
        )
        replacement = await self._session.scalar(
            select(FinancialEvent)
            .where(
                FinancialEvent.workspace_id == context.workspace_id,
                FinancialEvent.replacement_for_financial_event_id == event_id,
            )
            .order_by(FinancialEvent.created_at.desc())
        )
        return FinancialEventLifecycleRecord(
            original=self._event_record(original),
            reversal=self._event_record(reversal) if reversal is not None else None,
            replacement=(self._event_record(replacement) if replacement is not None else None),
        )

    async def validate_event_category(
        self,
        context: AuthorizationContext,
        *,
        category_id: UUID,
        event_kind: str,
        activity_classification_code: str,
    ) -> None:
        await self._revalidate(context)
        require_capability(context, Capability.CREATE_FINANCIAL_SUBMISSION)
        category = await self._session.scalar(
            select(FinanceCategory)
            .where(
                FinanceCategory.workspace_id == context.workspace_id,
                FinanceCategory.id == category_id,
                FinanceCategory.status == "ACTIVE",
            )
            .with_for_update()
        )
        if category is None:
            await self._audit_denial(context, AuditReason.RESOURCE_NOT_FOUND)
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        expected_applicability = "INCOME" if event_kind == "MANUAL_INCOME" else "EXPENSE"
        if category.applicability_code not in (expected_applicability, "BOTH"):
            raise InvalidFinanceCategory
        if (
            category.activity_classification_code is not None
            and category.activity_classification_code != activity_classification_code
        ):
            raise InvalidFinanceCategory

    async def _locked_category(
        self, context: AuthorizationContext, category_id: UUID
    ) -> FinanceCategory:
        await self._revalidate(context)
        category = await self._session.scalar(
            select(FinanceCategory)
            .where(
                FinanceCategory.workspace_id == context.workspace_id,
                FinanceCategory.id == category_id,
            )
            .with_for_update()
        )
        if category is None:
            await self._audit_denial(context, AuditReason.RESOURCE_NOT_FOUND)
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return category

    async def _require_mutable_version(
        self, context: AuthorizationContext, category: FinanceCategory, expected_version: int
    ) -> None:
        if category.version != expected_version:
            await self._audit_denial(context, AuditReason.STALE_VERSION)
            raise FinanceCategoryVersionMismatch
        if category.status != "ACTIVE":
            await self._audit_denial(context, AuditReason.INVALID_STATE_TRANSITION)
            raise FinanceCategoryStateConflict

    @staticmethod
    def _category_record(category: FinanceCategory) -> FinanceCategoryRecord:
        return FinanceCategoryRecord(
            id=category.id,
            display_name=category.display_name,
            applicability_code=category.applicability_code,
            activity_classification_code=category.activity_classification_code,
            status=category.status,
            version=category.version,
        )

    @staticmethod
    def _event_record(event: FinancialEvent) -> FinancialEventRecord:
        return FinancialEventRecord(
            id=event.id,
            event_kind=event.event_kind,
            cash_direction=event.cash_direction,
            activity_classification_code=event.activity_classification_code,
            occurred_on=event.occurred_on,
            finance_category_id=event.finance_category_id,
            amount=event.amount,
            currency_code=event.currency_code,
            payment_method_code=event.payment_method_code,
            counterparty_text=event.counterparty_text,
            reference_text=event.reference_text,
            notes=event.notes,
            approval_status=event.approval_status,
            posting_status=event.posting_status,
            version=event.version,
            created_at=event.created_at,
            archived_at=event.archived_at,
        )

    async def _audit(
        self,
        context: AuthorizationContext,
        action: AuditAction,
        resource_id: UUID,
        *,
        resource_type: AuditResourceType = AuditResourceType.FINANCE_CATEGORY,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=action,
                module=AuditModule.HOUSEHOLD_FINANCE,
                result=AuditResult.SUCCEEDED,
                correlation_id=context.correlation_id,
                resource_type=resource_type,
                resource_id=resource_id,
                source=AuditSource.API,
                context=AuditContext.FINANCE_ENTRY,
            )
        )

    async def _audit_denial(
        self,
        context: AuthorizationContext,
        reason: AuditReason,
        *,
        resource_type: AuditResourceType = AuditResourceType.FINANCE_CATEGORY,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=AuditAction.FINANCE_ACCESS_DENIED,
                module=AuditModule.HOUSEHOLD_FINANCE,
                result=AuditResult.DENIED,
                correlation_id=context.correlation_id,
                resource_type=resource_type,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.FINANCE_ENTRY,
            )
        )

    async def _revalidate(self, context: AuthorizationContext) -> None:
        statement = (
            select(WorkspaceMembership.id)
            .select_from(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .join(WorkspaceModule, WorkspaceModule.workspace_id == Workspace.id)
            .where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.id == context.membership_id,
                WorkspaceMembership.user_account_id == context.actor_account_id,
                WorkspaceMembership.role == context.role.value,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.status == "ACTIVE",
                Workspace.status == "ACTIVE",
                WorkspaceModule.module_code == "HOUSEHOLD_FINANCE",
                WorkspaceModule.enabled.is_(True),
            )
        )
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
