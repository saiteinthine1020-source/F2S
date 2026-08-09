"""Pure Workspace Access authorization-context and capability tests."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    capabilities_for,
    require_capability,
)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (WorkspaceRole.ADMIN, frozenset(Capability)),
        (
            WorkspaceRole.CONTRIBUTOR,
            frozenset(
                {
                    Capability.ACCESS_WORKSPACE,
                    Capability.CREATE_FINANCIAL_SUBMISSION,
                    Capability.EDIT_OWN_PENDING_SUBMISSION,
                }
            ),
        ),
        (
            WorkspaceRole.ADVISOR,
            frozenset(
                {
                    Capability.ACCESS_WORKSPACE,
                    Capability.VIEW_OFFICIAL_BALANCES,
                    Capability.VIEW_REPORTS,
                    Capability.COMMENT_OR_FLAG,
                }
            ),
        ),
    ],
)
def test_phase_one_capability_decision_table(
    role: WorkspaceRole, expected: frozenset[Capability]
) -> None:
    """Every Phase 1 role receives exactly its server-owned capabilities."""
    assert capabilities_for(role) == expected


def test_authorization_context_is_immutable_and_derives_capabilities() -> None:
    """A caller cannot inject a capability set or mutate derived authority."""
    context = AuthorizationContext(
        actor_account_id=uuid4(),
        workspace_id=uuid4(),
        membership_id=uuid4(),
        role=WorkspaceRole.CONTRIBUTOR,
        correlation_id=uuid4(),
    )

    assert context.capabilities == capabilities_for(WorkspaceRole.CONTRIBUTOR)
    with pytest.raises(TypeError):
        AuthorizationContext(  # type: ignore[call-arg]
            actor_account_id=uuid4(),
            workspace_id=uuid4(),
            membership_id=uuid4(),
            role=WorkspaceRole.CONTRIBUTOR,
            correlation_id=uuid4(),
            capabilities=frozenset(Capability),
        )
    with pytest.raises(FrozenInstanceError):
        context.role = WorkspaceRole.ADMIN  # type: ignore[misc]


def test_contributor_restricted_administration_capability_is_denied_safely() -> None:
    """Contributor policy cannot be widened to administration or restricted totals."""
    context = AuthorizationContext(
        actor_account_id=uuid4(),
        workspace_id=uuid4(),
        membership_id=uuid4(),
        role=WorkspaceRole.CONTRIBUTOR,
        correlation_id=uuid4(),
    )

    for capability in (
        Capability.VIEW_OFFICIAL_BALANCES,
        Capability.VIEW_REPORTS,
        Capability.APPROVE_OR_REJECT_SUBMISSIONS,
        Capability.MANAGE_WORKSPACE_SETTINGS,
        Capability.MANAGE_MEMBERS,
        Capability.TRANSFER_OWNERSHIP,
    ):
        with pytest.raises(AuthorizationDenied) as failure:
            require_capability(context, capability)
        assert failure.value.code is DenialCode.PERMISSION_DENIED
        assert str(failure.value) == "PERMISSION_DENIED"
