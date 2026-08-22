"""Framework-free role, text, lifecycle, and replay tests for finance reviews."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyClaim,
    IdempotencyRepository,
    IdempotencyService,
    IdempotencyState,
    SafeOutcome,
)
from app.modules.household_finance import (
    FinanceCommandMetadata,
    FinanceRepository,
    FinancialEventReviewRecord,
    FinancialReviewCreateCommand,
    FinancialReviewKind,
    FinancialReviewReason,
    FinancialReviewResolution,
    FinancialReviewService,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    WorkspaceRole,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


class FakeReviewRepository:
    def __init__(self) -> None:
        self.event_id = uuid4()
        self.created = 0
        self.resolved = 0
        self.record: FinancialEventReviewRecord | None = None

    async def list_event_reviews(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventReviewRecord, ...] | None:
        del context
        if event_id != self.event_id:
            return None
        return () if self.record is None else (self.record,)

    async def get_event_review(
        self, context: AuthorizationContext, *, review_id: UUID
    ) -> FinancialEventReviewRecord | None:
        del context
        return self.record if self.record is not None and self.record.id == review_id else None

    async def create_event_review(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventReviewRecord:
        self.created += 1
        self.record = FinancialEventReviewRecord(
            id=uuid4(),
            financial_event_id=cast(UUID, values["event_id"]),
            review_kind=cast(str, values["review_kind"]),
            body_text=cast(str, values["body_text"]),
            reason_code=cast(str | None, values["reason_code"]),
            flag_status="OPEN" if values["review_kind"] == "FLAG" else None,
            created_by_membership_id=context.membership_id,
            created_at=datetime.now(UTC),
            resolved_by_membership_id=None,
            resolved_at=None,
            resolution_code=None,
            version=1,
        )
        return self.record

    async def resolve_event_review(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventReviewRecord:
        assert self.record is not None
        self.resolved += 1
        self.record = replace(
            self.record,
            flag_status="RESOLVED",
            resolved_by_membership_id=context.membership_id,
            resolved_at=datetime.now(UTC),
            resolution_code=cast(str, values["resolution_code"]),
            version=2,
        )
        return self.record


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.claim_result = IdempotencyClaim(
            uuid4(), ClaimDisposition.STARTED, IdempotencyState.IN_PROGRESS, uuid4(), None
        )
        self.completed: SafeOutcome | None = None

    async def claim(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context, values
        return self.claim_result

    async def complete(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context
        self.completed = cast(SafeOutcome, values["outcome"])
        return replace(
            self.claim_result,
            disposition=ClaimDisposition.REPLAY,
            state=IdempotencyState.COMPLETED,
            outcome=self.completed,
        )

    async def fail(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        raise AssertionError((context, values))


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def _metadata() -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        uuid4(),
        OperationCode("CREATE_FINANCIAL_REVIEW"),
        IdempotencyKey("synthetic-review-key-0001"),
        RequestFingerprint.from_canonical_bytes(b"synthetic review"),
        Capability.COMMENT_OR_FLAG,
    )


def _service() -> tuple[FinancialReviewService, FakeReviewRepository, FakeIdempotencyRepository]:
    finance = FakeReviewRepository()
    idempotency = FakeIdempotencyRepository()
    return (
        FinancialReviewService(
            cast(FinanceRepository, finance),
            IdempotencyService(cast(IdempotencyRepository, idempotency)),
        ),
        finance,
        idempotency,
    )


def test_advisor_can_comment_and_flag_with_bounded_normalized_text() -> None:
    async def exercise() -> None:
        for command in (
            FinancialReviewCreateCommand(FinancialReviewKind.COMMENT, "  Check receipt  "),
            FinancialReviewCreateCommand(
                FinancialReviewKind.FLAG,
                "Possible duplicate",
                FinancialReviewReason.POSSIBLE_DUPLICATE,
            ),
        ):
            service, finance, idempotency = _service()
            record, replayed = await service.create(
                _context(WorkspaceRole.ADVISOR),
                event_id=finance.event_id,
                command=command,
                metadata=_metadata(),
            )
            assert not replayed
            assert record.body_text == command.body.strip()
            assert finance.created == 1
            assert idempotency.completed == SafeOutcome(
                "FINANCIAL_REVIEW_CREATED",
                201,
                "FINANCIAL_EVENT_REVIEW",
                record.id,
                1,
            )

    asyncio.run(exercise())


def test_role_action_matrix_and_kind_contract_are_enforced_before_storage() -> None:
    async def exercise() -> None:
        service, finance, _ = _service()
        with pytest.raises(AuthorizationDenied):
            await service.create(
                _context(WorkspaceRole.CONTRIBUTOR),
                event_id=finance.event_id,
                command=FinancialReviewCreateCommand(FinancialReviewKind.COMMENT, "No"),
                metadata=_metadata(),
            )
        with pytest.raises(AuthorizationDenied):
            await service.create(
                _context(WorkspaceRole.ADMIN),
                event_id=finance.event_id,
                command=FinancialReviewCreateCommand(
                    FinancialReviewKind.FLAG, "No", FinancialReviewReason.OTHER
                ),
                metadata=_metadata(),
            )
        with pytest.raises(ValueError, match="FLAG_REASON_REQUIRED"):
            await service.create(
                _context(WorkspaceRole.ADVISOR),
                event_id=finance.event_id,
                command=FinancialReviewCreateCommand(FinancialReviewKind.FLAG, "Missing"),
                metadata=_metadata(),
            )
        assert finance.created == 0

    asyncio.run(exercise())


def test_text_boundaries_admin_resolution_and_idempotent_replay() -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        with pytest.raises(ValueError, match="INVALID_REVIEW_BODY"):
            await service.create(
                _context(WorkspaceRole.ADVISOR),
                event_id=finance.event_id,
                command=FinancialReviewCreateCommand(FinancialReviewKind.COMMENT, "x" * 2001),
                metadata=_metadata(),
            )
        command = FinancialReviewCreateCommand(
            FinancialReviewKind.FLAG, "Review", FinancialReviewReason.OTHER
        )
        record, _ = await service.create(
            _context(WorkspaceRole.ADVISOR),
            event_id=finance.event_id,
            command=command,
            metadata=_metadata(),
        )
        idempotency.claim_result = replace(
            idempotency.claim_result,
            disposition=ClaimDisposition.REPLAY,
            state=IdempotencyState.COMPLETED,
            outcome=idempotency.completed,
        )
        replay, replayed = await service.create(
            _context(WorkspaceRole.ADVISOR),
            event_id=finance.event_id,
            command=command,
            metadata=_metadata(),
        )
        assert replayed and replay.id == record.id and finance.created == 1
        resolved = await service.resolve(
            _context(WorkspaceRole.ADMIN),
            review_id=record.id,
            expected_version=1,
            resolution_code=FinancialReviewResolution.REVIEWED_NO_CHANGE,
        )
        assert resolved.flag_status == "RESOLVED" and resolved.version == 2
        with pytest.raises(AuthorizationDenied):
            await service.resolve(
                _context(WorkspaceRole.ADVISOR),
                review_id=record.id,
                expected_version=2,
                resolution_code=FinancialReviewResolution.OTHER,
            )

    asyncio.run(exercise())
