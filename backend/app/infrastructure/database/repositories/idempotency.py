"""PostgreSQL-backed workspace-scoped idempotency coordination."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.support import IdempotencyRecord
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyClaim,
    IdempotencyKeyReused,
    IdempotencyState,
    IdempotencyStateConflict,
    SafeOutcome,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    require_capability,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint

_LEASE_DURATION = timedelta(minutes=2)
_TERMINAL_RETENTION = timedelta(days=14)


class SqlAlchemyIdempotencyRepository:
    """Claim one operation without committing the caller-owned transaction."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory

    async def claim(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        required_capability: Capability,
        operation: OperationCode,
        key: IdempotencyKey,
        fingerprint: RequestFingerprint,
    ) -> IdempotencyClaim:
        await self._revalidate(context, required_capability)
        now = self._now()
        record_id = uuid4()
        lease_token = self._token_factory()
        inserted_id = await self._session.scalar(
            insert(IdempotencyRecord)
            .values(
                id=record_id,
                workspace_id=context.workspace_id,
                actor_membership_id=context.membership_id,
                operation_id=operation_id,
                operation_code=operation.value,
                key_digest=key.digest(),
                request_fingerprint=fingerprint.value,
                state=IdempotencyState.IN_PROGRESS.value,
                lease_token=lease_token,
                lease_expires_at=now + _LEASE_DURATION,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing()
            .returning(IdempotencyRecord.id)
        )
        if inserted_id is not None:
            return IdempotencyClaim(
                inserted_id,
                ClaimDisposition.STARTED,
                IdempotencyState.IN_PROGRESS,
                lease_token,
                None,
            )

        record = await self._session.scalar(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.workspace_id == context.workspace_id,
                IdempotencyRecord.operation_code == operation.value,
                IdempotencyRecord.key_digest == key.digest(),
            )
            .with_for_update()
        )
        if record is None:
            raise IdempotencyKeyReused
        if record.actor_membership_id != context.membership_id:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if record.operation_id != operation_id or record.request_fingerprint != fingerprint.value:
            raise IdempotencyKeyReused

        if record.state in (IdempotencyState.COMPLETED.value, IdempotencyState.FAILED.value):
            if record.expires_at is not None and record.expires_at <= now:
                await self._session.execute(
                    delete(IdempotencyRecord).where(IdempotencyRecord.id == record.id)
                )
                await self._session.flush()
                return await self._create_after_expiry(
                    context,
                    operation_id=operation_id,
                    operation=operation,
                    key=key,
                    fingerprint=fingerprint,
                    now=now,
                )
            return self._claim(record, ClaimDisposition.REPLAY)

        disposition = (
            ClaimDisposition.IN_PROGRESS
            if record.lease_expires_at is not None and record.lease_expires_at > now
            else ClaimDisposition.RECOVERY_REQUIRED
        )
        return self._claim(record, disposition)

    async def complete(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim_id: UUID,
        lease_token: UUID,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim:
        return await self._finish(
            context,
            required_capability=required_capability,
            claim_id=claim_id,
            lease_token=lease_token,
            outcome=outcome,
            state=IdempotencyState.COMPLETED,
        )

    async def fail(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim_id: UUID,
        lease_token: UUID,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim:
        return await self._finish(
            context,
            required_capability=required_capability,
            claim_id=claim_id,
            lease_token=lease_token,
            outcome=outcome,
            state=IdempotencyState.FAILED,
        )

    async def _finish(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim_id: UUID,
        lease_token: UUID,
        outcome: SafeOutcome,
        state: IdempotencyState,
    ) -> IdempotencyClaim:
        await self._revalidate(context, required_capability)
        record = await self._session.scalar(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.id == claim_id,
                IdempotencyRecord.workspace_id == context.workspace_id,
                IdempotencyRecord.actor_membership_id == context.membership_id,
            )
            .with_for_update()
        )
        if record is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if record.state != IdempotencyState.IN_PROGRESS.value or record.lease_token != lease_token:
            raise IdempotencyStateConflict
        now = self._now()
        record.state = state.value
        record.lease_token = None
        record.lease_expires_at = None
        record.outcome_code = outcome.code
        record.http_status = outcome.http_status
        record.resource_type_code = outcome.resource_type
        record.resource_id = outcome.resource_id
        record.resource_version = outcome.resource_version
        record.updated_at = now
        record.completed_at = now
        record.expires_at = now + _TERMINAL_RETENTION
        await self._session.flush()
        return self._claim(record, ClaimDisposition.REPLAY)

    async def _create_after_expiry(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        operation: OperationCode,
        key: IdempotencyKey,
        fingerprint: RequestFingerprint,
        now: datetime,
    ) -> IdempotencyClaim:
        lease_token = self._token_factory()
        record = IdempotencyRecord(
            workspace_id=context.workspace_id,
            actor_membership_id=context.membership_id,
            operation_id=operation_id,
            operation_code=operation.value,
            key_digest=key.digest(),
            request_fingerprint=fingerprint.value,
            state=IdempotencyState.IN_PROGRESS.value,
            lease_token=lease_token,
            lease_expires_at=now + _LEASE_DURATION,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        await self._session.flush()
        return IdempotencyClaim(
            record.id,
            ClaimDisposition.STARTED,
            IdempotencyState.IN_PROGRESS,
            lease_token,
            None,
        )

    @staticmethod
    def _claim(record: IdempotencyRecord, disposition: ClaimDisposition) -> IdempotencyClaim:
        outcome = (
            SafeOutcome(
                code=record.outcome_code,
                http_status=record.http_status,
                resource_type=record.resource_type_code,
                resource_id=record.resource_id,
                resource_version=record.resource_version,
            )
            if record.outcome_code is not None and record.http_status is not None
            else None
        )
        return IdempotencyClaim(
            record.id,
            disposition,
            IdempotencyState(record.state),
            record.lease_token,
            outcome,
        )

    async def _revalidate(self, context: AuthorizationContext, capability: Capability) -> None:
        statement = (
            select(WorkspaceMembership.id)
            .select_from(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.id == context.membership_id,
                WorkspaceMembership.user_account_id == context.actor_account_id,
                WorkspaceMembership.role == context.role.value,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.status == "ACTIVE",
                Workspace.status == "ACTIVE",
            )
        )
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        require_capability(context, capability)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("IDEMPOTENCY_CLOCK_MUST_BE_TIMEZONE_AWARE")
        return value.astimezone(UTC)
