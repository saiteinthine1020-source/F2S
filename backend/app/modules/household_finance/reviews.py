"""Append-only Advisor comments and flags on approved financial events."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.modules.application_support import ClaimDisposition, IdempotencyService, SafeOutcome
from app.modules.household_finance.contracts import FinanceCommandMetadata
from app.modules.household_finance.events import (
    FinancialEventInProgress,
    FinancialEventRecoveryRequired,
    FinancialEventReplayUnavailable,
    normalize_optional_finance_text,
)
from app.modules.household_finance.repositories import (
    FinanceRepository,
    FinancialEventReviewRecord,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)


class FinancialReviewKind(StrEnum):
    COMMENT = "COMMENT"
    FLAG = "FLAG"


class FinancialReviewReason(StrEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    POSSIBLE_INCORRECT_AMOUNT = "POSSIBLE_INCORRECT_AMOUNT"
    POSSIBLE_INCORRECT_CATEGORY = "POSSIBLE_INCORRECT_CATEGORY"
    POSSIBLE_INCORRECT_DATE = "POSSIBLE_INCORRECT_DATE"
    OTHER = "OTHER"


class FinancialReviewResolution(StrEnum):
    REVIEWED_NO_CHANGE = "REVIEWED_NO_CHANGE"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    DUPLICATE_CONFIRMED = "DUPLICATE_CONFIRMED"
    OTHER = "OTHER"


class FinancialReviewStateConflict(Exception):
    """The review cannot make the requested lifecycle transition."""


class FinancialReviewVersionMismatch(Exception):
    """The review changed after the caller last read it."""


@dataclass(frozen=True, slots=True)
class FinancialReviewCreateCommand:
    kind: FinancialReviewKind
    body: str
    reason_code: FinancialReviewReason | None = None


class FinancialReviewService:
    """Apply role and lifecycle policy without depending on FastAPI or SQLAlchemy."""

    _CAPABILITY = Capability.COMMENT_OR_FLAG

    def __init__(self, repository: FinanceRepository, idempotency: IdempotencyService) -> None:
        self._repository = repository
        self._idempotency = idempotency

    async def list_reviews(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventReviewRecord, ...] | None:
        self._authorize_reader(context)
        return await self._repository.list_event_reviews(context, event_id=event_id)

    async def create(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        command: FinancialReviewCreateCommand,
        metadata: FinanceCommandMetadata,
    ) -> tuple[FinancialEventReviewRecord, bool]:
        self._authorize_create(context, command, metadata)
        body = normalize_optional_finance_text(
            command.body, maximum_length=2000, code="INVALID_REVIEW_BODY"
        )
        if body is None:
            raise ValueError("INVALID_REVIEW_BODY")
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
        if claim.disposition is ClaimDisposition.REPLAY:
            outcome = claim.outcome
            if outcome is not None and outcome.code == "RESOURCE_NOT_FOUND":
                raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
            if outcome is None or outcome.code != "FINANCIAL_REVIEW_CREATED":
                raise FinancialEventReplayUnavailable
            if outcome.resource_id is None:
                raise FinancialEventReplayUnavailable
            record = await self._repository.get_event_review(context, review_id=outcome.resource_id)
            if record is None:
                raise FinancialEventReplayUnavailable
            return record, True
        try:
            record = await self._repository.create_event_review(
                context,
                event_id=event_id,
                operation_id=metadata.operation_id,
                review_kind=command.kind.value,
                body_text=body,
                reason_code=(command.reason_code.value if command.reason_code else None),
            )
        except AuthorizationDenied:
            await self._idempotency.fail(
                context,
                required_capability=self._CAPABILITY,
                claim=claim,
                outcome=SafeOutcome("RESOURCE_NOT_FOUND", 404),
            )
            raise
        await self._idempotency.complete(
            context,
            required_capability=self._CAPABILITY,
            claim=claim,
            outcome=SafeOutcome(
                "FINANCIAL_REVIEW_CREATED",
                201,
                "FINANCIAL_EVENT_REVIEW",
                record.id,
                record.version,
            ),
        )
        return record, False

    async def resolve(
        self,
        context: AuthorizationContext,
        *,
        review_id: UUID,
        expected_version: int,
        resolution_code: FinancialReviewResolution,
    ) -> FinancialEventReviewRecord:
        if context.role is not WorkspaceRole.ADMIN:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, self._CAPABILITY)
        return await self._repository.resolve_event_review(
            context,
            review_id=review_id,
            expected_version=expected_version,
            resolution_code=resolution_code.value,
        )

    def _authorize_reader(self, context: AuthorizationContext) -> None:
        if context.role not in (WorkspaceRole.ADMIN, WorkspaceRole.ADVISOR):
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        require_capability(context, self._CAPABILITY)

    def _authorize_create(
        self,
        context: AuthorizationContext,
        command: FinancialReviewCreateCommand,
        metadata: FinanceCommandMetadata,
    ) -> None:
        self._authorize_reader(context)
        if metadata.required_capability is not self._CAPABILITY:
            raise ValueError("INVALID_REQUIRED_CAPABILITY")
        if metadata.operation.value != "CREATE_FINANCIAL_REVIEW":
            raise ValueError("INVALID_OPERATION_CODE")
        if context.role is WorkspaceRole.ADMIN and command.kind is not FinancialReviewKind.COMMENT:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        if command.kind is FinancialReviewKind.COMMENT and command.reason_code is not None:
            raise ValueError("COMMENT_REASON_NOT_ALLOWED")
        if command.kind is FinancialReviewKind.FLAG and command.reason_code is None:
            raise ValueError("FLAG_REASON_REQUIRED")
