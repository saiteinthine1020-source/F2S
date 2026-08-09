"""Framework-free audit intent, correlation, and append-only boundary tests."""

from typing import Any, cast
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.audit.correlation import CorrelationIdError, resolve_correlation_id
from app.modules.audit.events import (
    AuditAction,
    AuditActor,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.audit.ports import AuditWriter


def identity_event(**overrides: object) -> AuditEventIntent:
    """Build a safe synthetic global identity event."""
    values: dict[str, object] = {
        "scope": AuditScope.GLOBAL,
        "actor": AuditActor.user(uuid4()),
        "action": AuditAction.LOGIN_FAILED,
        "module": AuditModule.IDENTITY_SECURITY,
        "result": AuditResult.FAILED,
        "correlation_id": uuid4(),
        "reason": AuditReason.INVALID_CREDENTIALS,
        "source": AuditSource.API,
    }
    values.update(overrides)
    return AuditEventIntent(**cast(Any, values))


def test_correlation_is_generated_or_accepts_only_canonical_uuid() -> None:
    """Absent IDs are generated while malformed input is never echoed in errors."""
    generated = resolve_correlation_id(None)
    supplied = uuid4()

    assert generated.version == 4
    assert resolve_correlation_id(str(supplied).upper()) == supplied
    with pytest.raises(CorrelationIdError) as caught:
        resolve_correlation_id("secret-bearing invalid request value")
    assert caught.value.code.value == "INVALID_CORRELATION_ID"
    assert caught.value.correlation_id.version == 4
    assert "secret-bearing" not in str(caught.value)


@pytest.mark.parametrize(
    ("field", "unsafe_value", "error_code"),
    [
        ("action", "PASSWORD=synthetic", "INVALID_AUDIT_ACTION"),
        ("module", "raw-module", "INVALID_AUDIT_MODULE"),
        ("reason", "token=synthetic", "INVALID_AUDIT_REASON"),
        ("source", "Authorization header", "INVALID_AUDIT_SOURCE"),
        ("context", {"raw_payload": "synthetic"}, "INVALID_AUDIT_CONTEXT"),
    ],
)
def test_metadata_rejects_free_text_and_raw_values(
    field: str, unsafe_value: object, error_code: str
) -> None:
    """Only declared enums can enter the persisted metadata columns."""
    with pytest.raises(ValueError, match=error_code):
        identity_event(**{field: unsafe_value})


def test_scope_actor_resource_and_denial_invariants() -> None:
    """Invalid identity/workspace combinations and disclosed denial targets fail closed."""
    with pytest.raises(ValueError, match="WORKSPACE_EVENT_REQUIRES_WORKSPACE"):
        identity_event(scope=AuditScope.WORKSPACE)
    with pytest.raises(ValueError, match="MEMBERSHIP_ACTOR_REQUIRES_WORKSPACE_SCOPE"):
        identity_event(actor=AuditActor.user(uuid4(), uuid4()))
    with pytest.raises(ValueError, match="RESOURCE_ID_REQUIRES_TYPE"):
        identity_event(resource_id=uuid4())
    with pytest.raises(ValueError, match="DENIED_EVENT_MUST_NOT_DISCLOSE_RESOURCE_ID"):
        identity_event(
            result=AuditResult.DENIED,
            resource_type=AuditResourceType.WORKSPACE,
            resource_id=uuid4(),
        )


def test_concealed_denial_reuses_safe_error_correlation() -> None:
    """Denied evidence correlates to the response without storing the probed identifier."""
    correlation_id = uuid4()
    intent = AuditEventIntent.denied_cross_workspace(
        actor_account_id=uuid4(),
        correlation_id=correlation_id,
        source=AuditSource.API,
    )

    assert intent.correlation_id == correlation_id
    assert intent.reason is AuditReason.RESOURCE_NOT_FOUND
    assert intent.resource_type is AuditResourceType.WORKSPACE
    assert intent.resource_id is None
    assert intent.workspace_id is None


def test_application_audit_boundaries_are_append_only() -> None:
    """Neither the public port nor its SQLAlchemy adapter exposes mutation/removal methods."""
    port_methods = {
        name
        for name, value in AuditWriter.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    adapter_methods = {
        name
        for name, value in SqlAlchemyAuditWriter.__dict__.items()
        if callable(value) and not name.startswith("_")
    }

    assert port_methods == {"append"}
    assert adapter_methods == {"append"}
