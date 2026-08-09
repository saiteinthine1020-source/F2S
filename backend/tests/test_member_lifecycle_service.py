"""Membership transition-table and service boundary tests."""

import pytest

from app.modules.member_lifecycle import (
    InvalidMembershipTransition,
    MembershipMutation,
    MembershipOperation,
    MembershipStatus,
    OwnershipInvariantViolation,
    validate_transition,
)
from app.modules.workspace_access import WorkspaceRole


@pytest.mark.parametrize(
    ("status", "target"),
    [
        (MembershipStatus.PENDING, WorkspaceRole.ADVISOR),
        (MembershipStatus.ACTIVE, WorkspaceRole.ADVISOR),
        (MembershipStatus.SUSPENDED, WorkspaceRole.CONTRIBUTOR),
    ],
)
def test_role_changes_preserve_lifecycle_state(
    status: MembershipStatus, target: WorkspaceRole
) -> None:
    current = (
        WorkspaceRole.CONTRIBUTOR if target is WorkspaceRole.ADVISOR else WorkspaceRole.ADVISOR
    )
    assert validate_transition(
        current_role=current,
        current_status=status,
        mutation=MembershipMutation(MembershipOperation.CHANGE_ROLE, target),
    ) == (target, status)


@pytest.mark.parametrize(
    ("operation", "current", "expected"),
    [
        (MembershipOperation.SUSPEND, MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED),
        (
            MembershipOperation.REACTIVATE,
            MembershipStatus.SUSPENDED,
            MembershipStatus.ACTIVE,
        ),
        (MembershipOperation.REVOKE, MembershipStatus.PENDING, MembershipStatus.REVOKED),
        (MembershipOperation.REVOKE, MembershipStatus.ACTIVE, MembershipStatus.REVOKED),
        (MembershipOperation.REVOKE, MembershipStatus.SUSPENDED, MembershipStatus.REVOKED),
    ],
)
def test_documented_lifecycle_transitions(
    operation: MembershipOperation,
    current: MembershipStatus,
    expected: MembershipStatus,
) -> None:
    assert validate_transition(
        current_role=WorkspaceRole.CONTRIBUTOR,
        current_status=current,
        mutation=MembershipMutation(operation),
    ) == (WorkspaceRole.CONTRIBUTOR, expected)


@pytest.mark.parametrize(
    ("operation", "status"),
    [
        (MembershipOperation.SUSPEND, MembershipStatus.PENDING),
        (MembershipOperation.SUSPEND, MembershipStatus.SUSPENDED),
        (MembershipOperation.REACTIVATE, MembershipStatus.ACTIVE),
        (MembershipOperation.REACTIVATE, MembershipStatus.PENDING),
        (MembershipOperation.REVOKE, MembershipStatus.REVOKED),
        (MembershipOperation.CHANGE_ROLE, MembershipStatus.REVOKED),
    ],
)
def test_invalid_or_terminal_transitions_are_rejected(
    operation: MembershipOperation, status: MembershipStatus
) -> None:
    with pytest.raises(InvalidMembershipTransition):
        validate_transition(
            current_role=WorkspaceRole.CONTRIBUTOR,
            current_status=status,
            mutation=MembershipMutation(operation, WorkspaceRole.ADVISOR),
        )


@pytest.mark.parametrize("operation", list(MembershipOperation))
def test_admin_owner_is_never_a_generic_transition_target(
    operation: MembershipOperation,
) -> None:
    with pytest.raises(OwnershipInvariantViolation):
        validate_transition(
            current_role=WorkspaceRole.ADMIN,
            current_status=MembershipStatus.ACTIVE,
            mutation=MembershipMutation(operation, WorkspaceRole.CONTRIBUTOR),
        )


def test_same_role_and_admin_target_are_rejected() -> None:
    with pytest.raises(InvalidMembershipTransition):
        validate_transition(
            current_role=WorkspaceRole.CONTRIBUTOR,
            current_status=MembershipStatus.ACTIVE,
            mutation=MembershipMutation(MembershipOperation.CHANGE_ROLE, WorkspaceRole.CONTRIBUTOR),
        )
    with pytest.raises(InvalidMembershipTransition):
        validate_transition(
            current_role=WorkspaceRole.CONTRIBUTOR,
            current_status=MembershipStatus.ACTIVE,
            mutation=MembershipMutation(MembershipOperation.CHANGE_ROLE, WorkspaceRole.ADMIN),
        )
