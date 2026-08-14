"""Public cross-module canonical finance-event command and reference contract."""

from dataclasses import dataclass
from typing import Protocol, TypeVar
from uuid import UUID

from app.modules.workspace_access import AuthorizationContext, Capability
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


@dataclass(frozen=True, slots=True)
class FinanceCommandMetadata:
    operation_id: UUID
    operation: OperationCode
    idempotency_key: IdempotencyKey
    request_fingerprint: RequestFingerprint
    required_capability: Capability

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, UUID):
            raise ValueError("INVALID_OPERATION_ID")
        if not isinstance(self.operation, OperationCode):
            raise ValueError("INVALID_OPERATION_CODE")
        if not isinstance(self.idempotency_key, IdempotencyKey):
            raise ValueError("INVALID_IDEMPOTENCY_KEY")
        if not isinstance(self.request_fingerprint, RequestFingerprint):
            raise ValueError("INVALID_REQUEST_FINGERPRINT")
        if not isinstance(self.required_capability, Capability):
            raise ValueError("INVALID_REQUIRED_CAPABILITY")


@dataclass(frozen=True, slots=True)
class CanonicalFinanceEventReference:
    workspace_id: UUID
    event_id: UUID
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.workspace_id, UUID) or not isinstance(self.event_id, UUID):
            raise ValueError("INVALID_FINANCE_EVENT_REFERENCE")
        if self.version <= 0:
            raise ValueError("INVALID_FINANCE_EVENT_VERSION")


CommandT = TypeVar("CommandT", contravariant=True)


class CanonicalFinanceEventCommand(Protocol[CommandT]):
    """Only supported write boundary from another module into Household Finance."""

    async def execute(
        self,
        context: AuthorizationContext,
        *,
        command: CommandT,
        metadata: FinanceCommandMetadata,
    ) -> CanonicalFinanceEventReference: ...
