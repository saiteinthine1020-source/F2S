"""Framework-free canonical finance and idempotency contract tests."""

import asyncio
from typing import cast
from uuid import uuid4

import pytest

from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyClaim,
    IdempotencyRepository,
    IdempotencyService,
    IdempotencyState,
    IdempotencyStateConflict,
    SafeOutcome,
)
from app.modules.household_finance import (
    CanonicalFinanceEventReference,
    FinanceCommandMetadata,
)
from app.modules.workspace_access import AuthorizationContext, Capability, WorkspaceRole
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.claim_result = IdempotencyClaim(
            uuid4(), ClaimDisposition.STARTED, IdempotencyState.IN_PROGRESS, uuid4(), None
        )
        self.received: dict[str, object] = {}

    async def claim(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        self.received = {"context": context, **values}
        return self.claim_result

    async def complete(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        self.received = {"context": context, **values}
        return IdempotencyClaim(
            self.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.COMPLETED,
            None,
            cast(SafeOutcome, values["outcome"]),
        )

    async def fail(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        self.received = {"context": context, **values}
        return IdempotencyClaim(
            self.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.FAILED,
            None,
            cast(SafeOutcome, values["outcome"]),
        )


def _context() -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), WorkspaceRole.ADMIN, uuid4())


def test_identifiers_are_bounded_digest_only_and_redacted() -> None:
    key = IdempotencyKey("synthetic-key-0001")
    fingerprint = RequestFingerprint.from_canonical_bytes(b'{"kind":"income"}')
    assert len(key.digest()) == 64
    assert key.value not in repr(key)
    assert fingerprint.value not in repr(fingerprint)
    assert fingerprint == RequestFingerprint.from_canonical_bytes(b'{"kind":"income"}')
    assert fingerprint != RequestFingerprint.from_canonical_bytes(b'{"kind":"expense"}')

    for invalid in ("short", "contains space 0001", "x" * 129, "unicode-\u3042-000000"):
        with pytest.raises(ValueError, match="INVALID_IDEMPOTENCY_KEY"):
            IdempotencyKey(invalid)
    with pytest.raises(ValueError, match="INVALID_OPERATION_CODE"):
        OperationCode("create-event")
    with pytest.raises(ValueError, match="INVALID_REQUEST_FINGERPRINT"):
        RequestFingerprint("not-a-digest")


def test_safe_outcome_and_finance_reference_are_bounded() -> None:
    resource_id = uuid4()
    assert SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", resource_id, 1).resource_id == resource_id
    with pytest.raises(ValueError, match="INCOMPLETE_RESOURCE_OUTCOME"):
        SafeOutcome("CREATED", 201, resource_id=resource_id)
    with pytest.raises(ValueError, match="INVALID_SAFE_OUTCOME"):
        SafeOutcome("CREATED", 99)
    with pytest.raises(ValueError, match="INVALID_FINANCE_EVENT_VERSION"):
        CanonicalFinanceEventReference(uuid4(), uuid4(), 0)


def test_service_preserves_the_caller_owned_transaction_contract() -> None:
    async def exercise() -> None:
        repository = FakeIdempotencyRepository()
        service = IdempotencyService(cast(IdempotencyRepository, repository))
        context = _context()
        operation_id = uuid4()
        operation = OperationCode("CREATE_FINANCIAL_EVENT")
        key = IdempotencyKey("synthetic-key-0002")
        fingerprint = RequestFingerprint.from_canonical_bytes(b"canonical")
        claim = await service.begin(
            context,
            operation_id=operation_id,
            required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
            operation=operation,
            key=key,
            fingerprint=fingerprint,
        )
        outcome = SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", uuid4(), 1)
        completed = await service.complete(
            context,
            required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
            claim=claim,
            outcome=outcome,
        )
        assert completed.outcome == outcome
        assert repository.received["claim_id"] == claim.id
        assert repository.received["lease_token"] == claim.lease_token

        with pytest.raises(IdempotencyStateConflict):
            await service.complete(
                context,
                required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
                claim=completed,
                outcome=outcome,
            )

        metadata = FinanceCommandMetadata(
            operation_id, operation, key, fingerprint, Capability.CREATE_FINANCIAL_SUBMISSION
        )
        assert metadata.operation_id == operation_id

    asyncio.run(exercise())
