"""Manual income and expense command policy and idempotent orchestration."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from app.modules.application_support import ClaimDisposition, IdempotencyService, SafeOutcome
from app.modules.household_finance.categories import ActivityClassification
from app.modules.household_finance.contracts import (
    CanonicalFinanceEventReference,
    FinanceCommandMetadata,
)
from app.modules.household_finance.repositories import FinanceRepository, FinancialEventRecord
from app.modules.workspace_access import (
    AuthorizationContext,
    Capability,
    require_capability,
)
from app.shared_kernel import Money


class FinancialEventKind(StrEnum):
    MANUAL_INCOME = "MANUAL_INCOME"
    MANUAL_EXPENSE = "MANUAL_EXPENSE"


class CashDirection(StrEnum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


class PaymentMethod(StrEnum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_MONEY = "MOBILE_MONEY"
    CARD = "CARD"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class FinancialEventInProgress(Exception):
    """A matching command already owns the active execution lease."""


class FinancialEventRecoveryRequired(Exception):
    """A stale command must be reconciled before another execution."""


class FinancialEventReplayUnavailable(Exception):
    """Stored safe replay evidence no longer resolves to an accessible event."""


class InvalidFinanceCategory(Exception):
    """The selected local category is incompatible with the command."""


@dataclass(frozen=True, slots=True)
class ManualFinancialEventCommand:
    event_kind: FinancialEventKind
    activity_classification: ActivityClassification
    occurred_on: date
    finance_category_id: UUID
    amount: str
    currency_code: str
    payment_method: PaymentMethod
    counterparty: str | None = None
    reference: str | None = None
    notes: str | None = None


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_optional_finance_text(
    value: str | None, *, maximum_length: int, code: str
) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError(code)
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or len(normalized) > maximum_length:
        raise ValueError(code)
    if _CONTROL_CHARACTERS.search(normalized) is not None:
        raise ValueError(code)
    return normalized


class FinancialEventCommandService:
    """Create one manual canonical event inside the caller-owned transaction."""

    def __init__(
        self,
        finance_repository: FinanceRepository,
        idempotency_service: IdempotencyService,
    ) -> None:
        self._finance_repository = finance_repository
        self._idempotency_service = idempotency_service

    async def execute(
        self,
        context: AuthorizationContext,
        *,
        command: ManualFinancialEventCommand,
        metadata: FinanceCommandMetadata,
    ) -> CanonicalFinanceEventReference:
        record, _ = await self.create_manual(context, command=command, metadata=metadata)
        return CanonicalFinanceEventReference(context.workspace_id, record.id, record.version)

    async def create_manual(
        self,
        context: AuthorizationContext,
        *,
        command: ManualFinancialEventCommand,
        metadata: FinanceCommandMetadata,
    ) -> tuple[FinancialEventRecord, bool]:
        if metadata.required_capability is not Capability.CREATE_FINANCIAL_SUBMISSION:
            raise ValueError("INVALID_REQUIRED_CAPABILITY")
        require_capability(context, Capability.CREATE_FINANCIAL_SUBMISSION)
        money = Money.parse_ordinary(command.amount, command.currency_code)
        counterparty = normalize_optional_finance_text(
            command.counterparty,
            maximum_length=256,
            code="INVALID_COUNTERPARTY",
        )
        reference = normalize_optional_finance_text(
            command.reference,
            maximum_length=128,
            code="INVALID_REFERENCE",
        )
        notes = normalize_optional_finance_text(
            command.notes,
            maximum_length=2000,
            code="INVALID_NOTES",
        )
        await self._finance_repository.validate_event_category(
            context,
            category_id=command.finance_category_id,
            event_kind=command.event_kind.value,
            activity_classification_code=command.activity_classification.value,
        )
        claim = await self._idempotency_service.begin(
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
        if claim.disposition is ClaimDisposition.REPLAY:
            outcome = claim.outcome
            if (
                outcome is None
                or outcome.code != "CREATED"
                or outcome.resource_type != "FINANCIAL_EVENT"
                or outcome.resource_id is None
            ):
                raise FinancialEventReplayUnavailable
            record = await self._finance_repository.get_event(context, event_id=outcome.resource_id)
            if record is None:
                raise FinancialEventReplayUnavailable
            return record, True

        direction = (
            CashDirection.INFLOW
            if command.event_kind is FinancialEventKind.MANUAL_INCOME
            else CashDirection.OUTFLOW
        )
        record = await self._finance_repository.create_event(
            context,
            operation_id=metadata.operation_id,
            event_kind=command.event_kind.value,
            cash_direction=direction.value,
            activity_classification_code=command.activity_classification.value,
            occurred_on=command.occurred_on,
            finance_category_id=command.finance_category_id,
            amount=money.to_storage_amount(),
            currency_code=money.currency.code,
            payment_method_code=command.payment_method.value,
            counterparty_text=counterparty,
            reference_text=reference,
            notes=notes,
        )
        await self._idempotency_service.complete(
            context,
            required_capability=metadata.required_capability,
            claim=claim,
            outcome=SafeOutcome(
                "CREATED",
                201,
                "FINANCIAL_EVENT",
                record.id,
                record.version,
            ),
        )
        return record, False
