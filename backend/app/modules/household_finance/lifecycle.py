"""Append-only Admin correction, reversal, replacement, and archive policy."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyClaim,
    IdempotencyService,
    SafeOutcome,
)
from app.modules.household_finance.contracts import FinanceCommandMetadata
from app.modules.household_finance.events import (
    CashDirection,
    FinancialEventInProgress,
    FinancialEventKind,
    FinancialEventRecoveryRequired,
    FinancialEventReplayUnavailable,
    ManualFinancialEventCommand,
    normalize_optional_finance_text,
)
from app.modules.household_finance.repositories import (
    FinanceRepository,
    FinancialEventLifecycleRecord,
    FinancialEventRecord,
    FinancialEventReplacement,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)
from app.shared_kernel import Money


class FinancialEventLifecycleReason(StrEnum):
    DUPLICATE = "DUPLICATE"
    ENTERED_IN_ERROR = "ENTERED_IN_ERROR"
    INCORRECT_AMOUNT = "INCORRECT_AMOUNT"
    INCORRECT_CATEGORY = "INCORRECT_CATEGORY"
    INCORRECT_DATE = "INCORRECT_DATE"
    INCORRECT_CLASSIFICATION = "INCORRECT_CLASSIFICATION"
    INCORRECT_PAYMENT_METHOD = "INCORRECT_PAYMENT_METHOD"
    OTHER = "OTHER"


class FinancialEventLifecycleStateConflict(Exception):
    """The event is not eligible for the requested lifecycle command."""


@dataclass(frozen=True, slots=True)
class FinancialEventReversalCommand:
    occurred_on: date
    reason_code: FinancialEventLifecycleReason
    confirmed: bool


@dataclass(frozen=True, slots=True)
class FinancialEventCorrectionCommand:
    reversal_occurred_on: date
    reason_code: FinancialEventLifecycleReason
    confirmed: bool
    replacement: ManualFinancialEventCommand | None = None


@dataclass(frozen=True, slots=True)
class FinancialEventArchiveCommand:
    reason_code: FinancialEventLifecycleReason
    confirmed: bool


class FinancialEventLifecycleService:
    """Run one privileged lifecycle transition through a caller-owned transaction."""

    _CAPABILITY = Capability.APPROVE_OR_REJECT_SUBMISSIONS

    def __init__(self, repository: FinanceRepository, idempotency: IdempotencyService) -> None:
        self._repository = repository
        self._idempotency = idempotency

    async def reverse(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        command: FinancialEventReversalCommand,
        metadata: FinanceCommandMetadata,
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        self._authorize(context, metadata, "REVERSE_FINANCIAL_EVENT")
        self._require_confirmation(command.confirmed)
        return await self._execute_reversal(
            context,
            event_id=event_id,
            expected_version=expected_version,
            occurred_on=command.occurred_on,
            reason_code=command.reason_code.value,
            correction=False,
            replacement=None,
            metadata=metadata,
            outcome_code="REVERSED",
        )

    async def correct(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        command: FinancialEventCorrectionCommand,
        metadata: FinanceCommandMetadata,
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        self._authorize(context, metadata, "CORRECT_FINANCIAL_EVENT")
        self._require_confirmation(command.confirmed)
        replacement = await self._replacement(context, command.replacement)
        return await self._execute_reversal(
            context,
            event_id=event_id,
            expected_version=expected_version,
            occurred_on=command.reversal_occurred_on,
            reason_code=command.reason_code.value,
            correction=True,
            replacement=replacement,
            metadata=metadata,
            outcome_code="CORRECTED",
        )

    async def archive(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        command: FinancialEventArchiveCommand,
        metadata: FinanceCommandMetadata,
    ) -> tuple[FinancialEventRecord, bool]:
        self._authorize(context, metadata, "ARCHIVE_FINANCIAL_EVENT")
        self._require_confirmation(command.confirmed)
        claim = await self._begin(context, metadata)
        if claim.disposition is ClaimDisposition.REPLAY:
            outcome = claim.outcome
            if outcome is not None and outcome.code == "RESOURCE_NOT_FOUND":
                raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
            if outcome is not None and outcome.code == "VERSION_MISMATCH":
                from app.modules.household_finance.events import FinancialEventVersionMismatch

                raise FinancialEventVersionMismatch
            if outcome is not None and outcome.code == "INVALID_STATE_TRANSITION":
                raise FinancialEventLifecycleStateConflict
            if outcome is None or outcome.code != "ARCHIVED" or outcome.resource_id != event_id:
                raise FinancialEventReplayUnavailable
            record = await self._repository.get_event(context, event_id=event_id)
            if record is None or record.archived_at is None:
                raise FinancialEventReplayUnavailable
            return record, True
        try:
            record = await self._repository.archive_event(
                context,
                event_id=event_id,
                expected_version=expected_version,
                reason_code=command.reason_code.value,
            )
        except Exception as error:
            await self._record_failure(context, metadata, claim, error)
            raise
        await self._complete(context, metadata, claim, "ARCHIVED", record.id, record.version)
        return record, False

    async def _execute_reversal(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        occurred_on: date,
        reason_code: str,
        correction: bool,
        replacement: FinancialEventReplacement | None,
        metadata: FinanceCommandMetadata,
        outcome_code: str,
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        claim = await self._begin(context, metadata)
        if claim.disposition is ClaimDisposition.REPLAY:
            outcome = claim.outcome
            if outcome is not None and outcome.code == "RESOURCE_NOT_FOUND":
                raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
            if outcome is not None and outcome.code == "VERSION_MISMATCH":
                from app.modules.household_finance.events import FinancialEventVersionMismatch

                raise FinancialEventVersionMismatch
            if outcome is not None and outcome.code == "INVALID_STATE_TRANSITION":
                raise FinancialEventLifecycleStateConflict
            if outcome is None or outcome.code != outcome_code or outcome.resource_id != event_id:
                raise FinancialEventReplayUnavailable
            result = await self._repository.get_lifecycle_result(context, event_id=event_id)
            if result is None or result.reversal is None:
                raise FinancialEventReplayUnavailable
            return result, True
        try:
            result = await self._repository.reverse_event(
                context,
                event_id=event_id,
                expected_version=expected_version,
                operation_id=metadata.operation_id,
                occurred_on=occurred_on,
                reason_code=reason_code,
                correction=correction,
                replacement=replacement,
            )
        except Exception as error:
            await self._record_failure(context, metadata, claim, error)
            raise
        await self._complete(
            context, metadata, claim, outcome_code, result.original.id, result.original.version
        )
        return result, False

    async def _replacement(
        self, context: AuthorizationContext, command: ManualFinancialEventCommand | None
    ) -> FinancialEventReplacement | None:
        if command is None:
            return None
        money = Money.parse_ordinary(command.amount, command.currency_code)
        await self._repository.validate_event_category(
            context,
            category_id=command.finance_category_id,
            event_kind=command.event_kind.value,
            activity_classification_code=command.activity_classification.value,
        )
        direction = (
            CashDirection.INFLOW
            if command.event_kind is FinancialEventKind.MANUAL_INCOME
            else CashDirection.OUTFLOW
        )
        return FinancialEventReplacement(
            command.event_kind.value,
            direction.value,
            command.activity_classification.value,
            command.occurred_on,
            command.finance_category_id,
            money.to_storage_amount(),
            money.currency.code,
            command.payment_method.value,
            normalize_optional_finance_text(
                command.counterparty, maximum_length=256, code="INVALID_COUNTERPARTY"
            ),
            normalize_optional_finance_text(
                command.reference, maximum_length=128, code="INVALID_REFERENCE"
            ),
            normalize_optional_finance_text(
                command.notes, maximum_length=2000, code="INVALID_NOTES"
            ),
        )

    def _authorize(
        self, context: AuthorizationContext, metadata: FinanceCommandMetadata, operation: str
    ) -> None:
        if metadata.required_capability is not self._CAPABILITY:
            raise ValueError("INVALID_REQUIRED_CAPABILITY")
        if metadata.operation.value != operation:
            raise ValueError("INVALID_OPERATION_CODE")
        if context.role is not WorkspaceRole.ADMIN:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, self._CAPABILITY)

    @staticmethod
    def _require_confirmation(value: bool) -> None:
        if type(value) is not bool or value is not True:
            raise ValueError("CONFIRMATION_REQUIRED")

    async def _begin(
        self, context: AuthorizationContext, metadata: FinanceCommandMetadata
    ) -> IdempotencyClaim:
        claim = await self._idempotency.begin(
            context,
            operation_id=metadata.operation_id,
            required_capability=metadata.required_capability,
            operation=metadata.operation,
            key=metadata.idempotency_key,
            fingerprint=metadata.request_fingerprint,
        )
        if claim.disposition is ClaimDisposition.IN_PROGRESS:
            raise FinancialEventInProgress
        if claim.disposition is ClaimDisposition.RECOVERY_REQUIRED:
            raise FinancialEventRecoveryRequired
        return claim

    async def _record_failure(
        self,
        context: AuthorizationContext,
        metadata: FinanceCommandMetadata,
        claim: IdempotencyClaim,
        error: Exception,
    ) -> None:
        from app.modules.household_finance.events import FinancialEventVersionMismatch

        if isinstance(error, AuthorizationDenied):
            outcome = SafeOutcome("RESOURCE_NOT_FOUND", 404)
        elif isinstance(error, FinancialEventVersionMismatch):
            outcome = SafeOutcome("VERSION_MISMATCH", 412)
        elif isinstance(error, FinancialEventLifecycleStateConflict):
            outcome = SafeOutcome("INVALID_STATE_TRANSITION", 409)
        else:
            return
        await self._idempotency.fail(
            context, required_capability=metadata.required_capability, claim=claim, outcome=outcome
        )

    async def _complete(
        self,
        context: AuthorizationContext,
        metadata: FinanceCommandMetadata,
        claim: IdempotencyClaim,
        code: str,
        event_id: UUID,
        version: int,
    ) -> None:
        await self._idempotency.complete(
            context,
            required_capability=metadata.required_capability,
            claim=claim,
            outcome=SafeOutcome(code, 200, "FINANCIAL_EVENT", event_id, version),
        )
