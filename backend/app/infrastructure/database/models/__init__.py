"""SQLAlchemy mappings registered with the shared metadata."""

from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.finance import FinanceCategory, FinancialEvent
from app.infrastructure.database.models.identity import BootstrapState, UserAccount
from app.infrastructure.database.models.identity_security import (
    ActivationChallenge,
    AuthSession,
    RecoveryChallenge,
)
from app.infrastructure.database.models.support import IdempotencyRecord
from app.infrastructure.database.models.workspace_access import (
    OwnershipTransfer,
    Workspace,
    WorkspaceMembership,
    WorkspaceModule,
)

__all__ = [
    "ActivationChallenge",
    "AuditEvent",
    "AuthSession",
    "BootstrapState",
    "FinanceCategory",
    "FinancialEvent",
    "IdempotencyRecord",
    "OwnershipTransfer",
    "RecoveryChallenge",
    "UserAccount",
    "Workspace",
    "WorkspaceMembership",
    "WorkspaceModule",
]
