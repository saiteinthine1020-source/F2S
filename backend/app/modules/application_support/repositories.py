"""Framework-free durable idempotency persistence contracts."""

from typing import Protocol
from uuid import UUID

from app.modules.application_support.idempotency import IdempotencyClaim, SafeOutcome
from app.modules.workspace_access import AuthorizationContext, Capability
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


class IdempotencyRepository(Protocol):
    async def claim(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        required_capability: Capability,
        operation: OperationCode,
        key: IdempotencyKey,
        fingerprint: RequestFingerprint,
    ) -> IdempotencyClaim: ...

    async def complete(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim_id: UUID,
        lease_token: UUID,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim: ...

    async def fail(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim_id: UUID,
        lease_token: UUID,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim: ...
