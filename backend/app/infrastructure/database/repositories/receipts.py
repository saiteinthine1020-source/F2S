"""SQLAlchemy persistence for protected finance receipt metadata and links."""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.finance import (
    FinancialEvent,
    FinancialEventFile,
    ProtectedFile,
)
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
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
from app.modules.household_finance.receipts import (
    ProtectedFileState,
    ReceiptRecord,
    ReceiptStateConflict,
    ReceiptStorageRecord,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)


class SqlAlchemyReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        operation_id: UUID,
        filename: str,
        media_type: str,
        expected_size: int,
        expected_sha256: str,
        storage_key: str,
        expires_at: datetime,
    ) -> ReceiptRecord:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        event = await self._event_for_write(context, event_id, lock=True)
        if event is None:
            await self._denial(context, AuditReason.RESOURCE_NOT_FOUND)
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        now = datetime.now(UTC)
        protected = ProtectedFile(
            workspace_id=context.workspace_id,
            purpose_code="FINANCIAL_RECEIPT",
            state="PENDING",
            declared_media_type=media_type,
            sanitized_filename=filename,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            storage_key=storage_key,
            operation_id=operation_id,
            created_by_membership_id=context.membership_id,
            created_at=now,
            reservation_expires_at=expires_at,
            version=1,
        )
        self._session.add(protected)
        await self._session.flush()
        link = FinancialEventFile(
            workspace_id=context.workspace_id,
            financial_event_id=event.id,
            protected_file_id=protected.id,
            attachment_role="RECEIPT",
            attached_by_membership_id=context.membership_id,
            attached_at=now,
        )
        self._session.add(link)
        await self._session.flush()
        await self._audit(context, AuditAction.FINANCIAL_RECEIPT_RESERVED, protected.id)
        await self._audit(context, AuditAction.FINANCIAL_RECEIPT_LINKED, protected.id)
        return self._record(protected, event.id)

    async def list_receipts(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[ReceiptRecord, ...] | None:
        if await self._event_for_read(context, event_id) is None:
            await self._denial(context, AuditReason.RESOURCE_NOT_FOUND)
            return None
        rows = (
            await self._session.execute(
                select(ProtectedFile, FinancialEventFile)
                .join(
                    FinancialEventFile,
                    and_(
                        FinancialEventFile.workspace_id == ProtectedFile.workspace_id,
                        FinancialEventFile.protected_file_id == ProtectedFile.id,
                    ),
                )
                .where(
                    ProtectedFile.workspace_id == context.workspace_id,
                    FinancialEventFile.financial_event_id == event_id,
                    FinancialEventFile.removed_at.is_(None),
                )
                .order_by(FinancialEventFile.attached_at, FinancialEventFile.id)
            )
        ).all()
        return tuple(self._record(file, link.financial_event_id) for file, link in rows)

    async def get_for_upload(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        row = await self._linked_file(context, receipt_id, write=True, lock=True)
        return None if row is None else self._storage_record(*row)

    async def mark_quarantined(
        self,
        context: AuthorizationContext,
        *,
        receipt_id: UUID,
        actual_size: int,
        actual_sha256: str,
        detected_media_type: str,
    ) -> ReceiptStorageRecord:
        row = await self._linked_file(context, receipt_id, write=True, lock=True)
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        file, link = row
        if file.state != "PENDING":
            raise ReceiptStateConflict
        file.state = "QUARANTINED"
        file.actual_size = actual_size
        file.actual_sha256 = actual_sha256
        file.detected_media_type = detected_media_type
        file.uploaded_at = datetime.now(UTC)
        file.version += 1
        await self._session.flush()
        await self._audit(context, AuditAction.FINANCIAL_RECEIPT_QUARANTINED, file.id)
        return self._storage_record(file, link)

    async def mark_available(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord:
        row = await self._linked_file(context, receipt_id, write=True, lock=True)
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        file, link = row
        if file.state != "QUARANTINED":
            raise ReceiptStateConflict
        now = datetime.now(UTC)
        file.state = "AVAILABLE"
        file.scanned_at = now
        file.available_at = now
        file.version += 1
        await self._session.flush()
        await self._audit(context, AuditAction.FINANCIAL_RECEIPT_AVAILABLE, file.id)
        return self._storage_record(file, link)

    async def mark_failed(
        self, context: AuthorizationContext, *, receipt_id: UUID, failure_code: str
    ) -> ReceiptStorageRecord:
        row = await self._linked_file(context, receipt_id, write=True, lock=True)
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        file, link = row
        if file.state not in ("PENDING", "QUARANTINED"):
            raise ReceiptStateConflict
        now = datetime.now(UTC)
        file.state = "FAILED"
        file.failure_code = failure_code
        file.scanned_at = now if file.uploaded_at is not None else None
        file.cleanup_after = now + timedelta(hours=24)
        file.version += 1
        await self._session.flush()
        return self._storage_record(file, link)

    async def mark_expired(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord:
        row = await self._linked_file(context, receipt_id, write=True, lock=True)
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        file, link = row
        if file.state != "PENDING":
            raise ReceiptStateConflict
        now = datetime.now(UTC)
        file.state = "EXPIRED"
        file.failure_code = "RESERVATION_EXPIRED"
        file.cleanup_after = now
        file.version += 1
        await self._session.flush()
        return self._storage_record(file, link)

    async def get_for_download(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None:
        row = await self._linked_file(context, receipt_id, write=False, lock=False)
        if row is None or row[0].state != ProtectedFileState.AVAILABLE:
            await self._denial(context, AuditReason.RESOURCE_NOT_FOUND)
            return None
        return self._storage_record(*row)

    async def get_status(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptRecord | None:
        row = await self._linked_file(context, receipt_id, write=False, lock=False)
        return None if row is None else self._record(row[0], row[1].financial_event_id)

    async def remove(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        receipt_id: UUID,
        operation_id: UUID,
        reason_code: str,
    ) -> ReceiptRecord:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        event = await self._event_for_write(context, event_id, lock=True)
        if event is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        row = await self._session.execute(
            select(ProtectedFile, FinancialEventFile)
            .join(
                FinancialEventFile,
                and_(
                    FinancialEventFile.workspace_id == ProtectedFile.workspace_id,
                    FinancialEventFile.protected_file_id == ProtectedFile.id,
                ),
            )
            .where(
                ProtectedFile.workspace_id == context.workspace_id,
                ProtectedFile.id == receipt_id,
                FinancialEventFile.financial_event_id == event_id,
                FinancialEventFile.removed_at.is_(None),
            )
            .with_for_update()
        )
        result = row.one_or_none()
        if result is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        file, link = result
        now = datetime.now(UTC)
        link.removed_at = now
        link.removed_by_membership_id = context.membership_id
        link.removal_reason = reason_code
        link.removal_operation_id = operation_id
        await self._session.flush()
        await self._audit(context, AuditAction.FINANCIAL_RECEIPT_REMOVED, file.id)
        return self._record(file, event_id)

    async def due_for_cleanup(self, *, now: datetime) -> tuple[ReceiptStorageRecord, ...]:
        rows = (
            await self._session.scalars(
                select(ProtectedFile)
                .where(
                    or_(
                        and_(
                            ProtectedFile.state.in_(("FAILED", "EXPIRED")),
                            ProtectedFile.cleanup_after <= now,
                        ),
                        and_(
                            ProtectedFile.state == "PENDING",
                            ProtectedFile.reservation_expires_at <= now,
                        ),
                        and_(
                            ProtectedFile.state == "QUARANTINED",
                            ProtectedFile.uploaded_at <= now - timedelta(hours=24),
                        ),
                    ),
                    ProtectedFile.deleted_at.is_(None),
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for file in rows:
            if file.state == "PENDING":
                file.state = "EXPIRED"
                file.failure_code = "RESERVATION_EXPIRED"
                file.cleanup_after = now
                file.version += 1
            elif file.state == "QUARANTINED":
                file.state = "FAILED"
                file.failure_code = "SCANNER_UNAVAILABLE"
                file.scanned_at = now
                file.cleanup_after = now
                file.version += 1
        await self._session.flush()
        return tuple(
            ReceiptStorageRecord(
                self._record(file, UUID(int=0)), file.storage_key, file.actual_sha256
            )
            for file in rows
        )

    async def mark_deleted(self, *, receipt_id: UUID, now: datetime) -> None:
        file = await self._session.scalar(
            select(ProtectedFile).where(ProtectedFile.id == receipt_id).with_for_update()
        )
        if file is None or file.state not in ("FAILED", "EXPIRED"):
            raise ReceiptStateConflict
        file.state = "DELETED"
        file.deleted_at = now
        file.version += 1
        await self._session.flush()
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=file.workspace_id,
                actor=AuditActor.system(),
                action=AuditAction.FINANCIAL_RECEIPT_DELETED_BY_RETENTION,
                module=AuditModule.HOUSEHOLD_FINANCE,
                result=AuditResult.SUCCEEDED,
                correlation_id=UUID(int=0),
                resource_type=AuditResourceType.PROTECTED_FILE,
                resource_id=file.id,
                source=AuditSource.BACKGROUND_JOB,
                context=AuditContext.FINANCE_RECEIPT,
            )
        )

    async def _event_for_read(
        self, context: AuthorizationContext, event_id: UUID
    ) -> FinancialEvent | None:
        visible = await SqlAlchemyFinanceRepository(self._session).get_visible_event(
            context, event_id=event_id
        )
        if visible is None:
            return None
        return cast(
            FinancialEvent | None,
            await self._session.scalar(
                select(FinancialEvent).where(
                    FinancialEvent.workspace_id == context.workspace_id,
                    FinancialEvent.id == event_id,
                    FinancialEvent.event_kind == "MANUAL_EXPENSE",
                ),
            ),
        )

    async def _event_for_write(
        self, context: AuthorizationContext, event_id: UUID, *, lock: bool
    ) -> FinancialEvent | None:
        await SqlAlchemyFinanceRepository(self._session).get_event(context, event_id=event_id)
        statement = select(FinancialEvent).where(
            FinancialEvent.workspace_id == context.workspace_id,
            FinancialEvent.id == event_id,
            FinancialEvent.event_kind == "MANUAL_EXPENSE",
            FinancialEvent.archived_at.is_(None),
            FinancialEvent.approval_status != "REJECTED",
        )
        if context.role is WorkspaceRole.CONTRIBUTOR:
            statement = statement.where(
                FinancialEvent.created_by_membership_id == context.membership_id,
                FinancialEvent.approval_status == "PENDING",
            )
        elif context.role is not WorkspaceRole.ADMIN:
            return None
        if lock:
            statement = statement.with_for_update()
        return cast(FinancialEvent | None, await self._session.scalar(statement))

    async def _linked_file(
        self,
        context: AuthorizationContext,
        receipt_id: UUID,
        *,
        write: bool,
        lock: bool,
    ) -> tuple[ProtectedFile, FinancialEventFile] | None:
        await SqlAlchemyFinanceRepository(self._session).revalidate_context(context)
        statement = (
            select(ProtectedFile, FinancialEventFile, FinancialEvent)
            .join(
                FinancialEventFile,
                and_(
                    FinancialEventFile.workspace_id == ProtectedFile.workspace_id,
                    FinancialEventFile.protected_file_id == ProtectedFile.id,
                ),
            )
            .join(
                FinancialEvent,
                and_(
                    FinancialEvent.workspace_id == FinancialEventFile.workspace_id,
                    FinancialEvent.id == FinancialEventFile.financial_event_id,
                ),
            )
            .where(
                ProtectedFile.workspace_id == context.workspace_id,
                ProtectedFile.id == receipt_id,
                ProtectedFile.purpose_code == "FINANCIAL_RECEIPT",
                FinancialEventFile.removed_at.is_(None),
            )
        )
        if write:
            require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
            if context.role is WorkspaceRole.CONTRIBUTOR:
                statement = statement.where(
                    ProtectedFile.created_by_membership_id == context.membership_id,
                    FinancialEvent.created_by_membership_id == context.membership_id,
                    FinancialEvent.approval_status == "PENDING",
                )
            elif context.role is not WorkspaceRole.ADMIN:
                return None
        else:
            if context.role is WorkspaceRole.ADVISOR:
                statement = statement.where(FinancialEvent.approval_status == "APPROVED")
            elif context.role is WorkspaceRole.CONTRIBUTOR:
                statement = statement.where(
                    FinancialEvent.created_by_membership_id == context.membership_id
                )
        if lock:
            statement = statement.with_for_update()
        result = (await self._session.execute(statement)).one_or_none()
        return None if result is None else (result[0], result[1])

    @staticmethod
    def _record(file: ProtectedFile, event_id: UUID) -> ReceiptRecord:
        return ReceiptRecord(
            file.id,
            event_id,
            file.state,
            file.declared_media_type,
            file.sanitized_filename,
            file.expected_size,
            file.expected_sha256,
            file.created_at,
            file.reservation_expires_at,
            file.version,
            file.failure_code,
        )

    def _storage_record(
        self, file: ProtectedFile, link: FinancialEventFile
    ) -> ReceiptStorageRecord:
        return ReceiptStorageRecord(
            self._record(file, link.financial_event_id), file.storage_key, file.actual_sha256
        )

    async def _audit(
        self, context: AuthorizationContext, action: AuditAction, resource_id: UUID
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
                resource_type=AuditResourceType.PROTECTED_FILE,
                resource_id=resource_id,
                source=AuditSource.API,
                context=AuditContext.FINANCE_RECEIPT,
            )
        )

    async def _denial(self, context: AuthorizationContext, reason: AuditReason) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=AuditAction.FINANCE_ACCESS_DENIED,
                module=AuditModule.HOUSEHOLD_FINANCE,
                result=AuditResult.DENIED,
                correlation_id=context.correlation_id,
                resource_type=AuditResourceType.PROTECTED_FILE,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.FINANCE_RECEIPT,
            )
        )
