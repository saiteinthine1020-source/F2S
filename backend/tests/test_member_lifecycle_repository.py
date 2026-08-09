"""PostgreSQL membership lifecycle, isolation, session, and audit tests."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity_security import ActivationChallenge, AuthSession
from app.infrastructure.database.models.workspace_access import WorkspaceMembership
from app.infrastructure.database.repositories.member_lifecycle import (
    SqlAlchemyMemberLifecycleRepository,
)
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.member_lifecycle import (
    MemberLifecycleService,
    MembershipStatus,
    MemberVersionMismatch,
    OwnershipInvariantViolation,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)


@dataclass(frozen=True, slots=True)
class Fixture:
    workspace_a: UUID
    workspace_b: UUID
    admin_account: UUID
    admin_membership: UUID
    member_account: UUID
    member_membership: UUID
    pending_account: UUID
    pending_membership: UUID
    pending_challenge: UUID
    foreign_membership: UUID
    first_session: UUID


async def _clear(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, recovery_challenges, activation_challenges, "
                    "auth_sessions, workspace_modules, workspace_memberships, workspaces, "
                    "user_accounts, bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


async def _seed(settings: Settings) -> Fixture:
    values = [uuid4() for _ in range(11)]
    fixture = Fixture(*values)
    foreign_admin, foreign_admin_membership, foreign_account = uuid4(), uuid4(), uuid4()
    suffix = uuid4().hex
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, status, preferred_language, timezone) "
                    "VALUES (:admin, :admin_email, 'Admin', 'ACTIVE', 'en', 'UTC'), "
                    "(:member, :member_email, 'Active Member', 'ACTIVE', 'en', 'UTC'), "
                    "(:pending, :pending_email, 'Pending Member', 'PENDING_ACTIVATION', "
                    "'ja', 'Asia/Tokyo'), "
                    "(:foreign_admin, :foreign_admin_email, 'Foreign Admin', 'ACTIVE', "
                    "'en', 'UTC'), (:foreign, :foreign_email, 'Foreign Member', 'ACTIVE', "
                    "'en', 'UTC')"
                ),
                {
                    "admin": fixture.admin_account,
                    "admin_email": f"lifecycle-admin-{suffix}@example.invalid",
                    "member": fixture.member_account,
                    "member_email": f"lifecycle-member-{suffix}@example.invalid",
                    "pending": fixture.pending_account,
                    "pending_email": f"lifecycle-pending-{suffix}@example.invalid",
                    "foreign_admin": foreign_admin,
                    "foreign_admin_email": f"lifecycle-foreign-admin-{suffix}@example.invalid",
                    "foreign": foreign_account,
                    "foreign_email": f"lifecycle-foreign-{suffix}@example.invalid",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "owner_membership_id, owner_role, owner_membership_status, status) VALUES "
                    "(:a, 'Workspace A', 'HOUSEHOLD', 'USD', 'UTC', 'en', :owner_a, "
                    "'ADMIN', 'ACTIVE', 'ACTIVE'), (:b, 'Workspace B', 'FARM', 'JPY', "
                    "'Asia/Tokyo', 'ja', :owner_b, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {
                    "a": fixture.workspace_a,
                    "b": fixture.workspace_b,
                    "owner_a": fixture.admin_membership,
                    "owner_b": foreign_admin_membership,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) VALUES "
                    "(:owner_a, :a, :admin, 'ADMIN', 'ACTIVE'), "
                    "(:member, :a, :member_account, 'CONTRIBUTOR', 'ACTIVE'), "
                    "(:pending, :a, :pending_account, 'ADVISOR', 'PENDING'), "
                    "(:owner_b, :b, :foreign_admin, 'ADMIN', 'ACTIVE'), "
                    "(:foreign_member, :b, :foreign_account, 'CONTRIBUTOR', 'ACTIVE')"
                ),
                {
                    "owner_a": fixture.admin_membership,
                    "a": fixture.workspace_a,
                    "admin": fixture.admin_account,
                    "member": fixture.member_membership,
                    "member_account": fixture.member_account,
                    "pending": fixture.pending_membership,
                    "pending_account": fixture.pending_account,
                    "owner_b": foreign_admin_membership,
                    "b": fixture.workspace_b,
                    "foreign_admin": foreign_admin,
                    "foreign_member": fixture.foreign_membership,
                    "foreign_account": foreign_account,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO auth_sessions "
                    "(id, user_account_id, family_id, access_credential_digest, "
                    "refresh_credential_digest, csrf_credential_digest, status, issued_at, "
                    "access_expires_at, refresh_idle_expires_at, absolute_expires_at, "
                    "last_used_at) VALUES (:id, :account, :family, :access, :refresh, :csrf, "
                    "'ACTIVE', current_timestamp - interval '1 hour', "
                    "current_timestamp + interval '1 hour', current_timestamp + interval '1 day', "
                    "current_timestamp + interval '30 days', current_timestamp)"
                ),
                {
                    "id": fixture.first_session,
                    "account": fixture.member_account,
                    "family": uuid4(),
                    "access": f"access-{suffix}",
                    "refresh": f"refresh-{suffix}",
                    "csrf": f"csrf-{suffix}",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO activation_challenges "
                    "(id, workspace_id, membership_id, user_account_id, challenge_digest, "
                    "status, issued_at, expires_at) VALUES (:id, :workspace, :membership, "
                    ":account, :digest, 'ISSUED', current_timestamp, "
                    "current_timestamp + interval '1 day')"
                ),
                {
                    "id": fixture.pending_challenge,
                    "workspace": fixture.workspace_a,
                    "membership": fixture.pending_membership,
                    "account": fixture.pending_account,
                    "digest": f"challenge-{suffix}",
                },
            )
    finally:
        await engine.dispose()
    return fixture


@pytest.mark.postgres
def test_membership_lifecycle_is_versioned_isolated_and_preserves_history(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        fixture = await _seed(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
        context = AuthorizationContext(
            fixture.admin_account,
            fixture.workspace_a,
            fixture.admin_membership,
            WorkspaceRole.ADMIN,
            uuid4(),
        )
        contributor_context = AuthorizationContext(
            fixture.member_account,
            fixture.workspace_a,
            fixture.member_membership,
            WorkspaceRole.CONTRIBUTOR,
            uuid4(),
        )
        try:
            async with transactional_session(sessions) as session:
                service = MemberLifecycleService(SqlAlchemyMemberLifecycleRepository(session))
                listed = await service.list_members(context)
                assert {member.id for member in listed} == {
                    fixture.admin_membership,
                    fixture.member_membership,
                    fixture.pending_membership,
                }
                assert fixture.foreign_membership not in {member.id for member in listed}
                assert (
                    next(
                        member for member in listed if member.id == fixture.member_membership
                    ).last_login_at
                    is not None
                )

                with pytest.raises(AuthorizationDenied):
                    await service.list_members(contributor_context)
                with pytest.raises(OwnershipInvariantViolation):
                    await service.revoke(
                        context,
                        membership_id=fixture.admin_membership,
                        expected_version=1,
                        now=now,
                    )
                with pytest.raises(AuthorizationDenied):
                    await service.revoke(
                        context,
                        membership_id=fixture.foreign_membership,
                        expected_version=1,
                        now=now,
                    )

                changed = await service.change_role(
                    context,
                    membership_id=fixture.member_membership,
                    expected_version=1,
                    role=WorkspaceRole.ADVISOR,
                    now=now,
                )
                assert (changed.role, changed.version) == (WorkspaceRole.ADVISOR, 2)
                assert (
                    await session.get(AuthSession, fixture.first_session)
                ).revoke_reason_code == "MEMBERSHIP_CHANGE_ROLE"  # type: ignore[union-attr]

                with pytest.raises(MemberVersionMismatch):
                    await service.suspend(
                        context,
                        membership_id=fixture.member_membership,
                        expected_version=1,
                        now=now,
                    )
                suspended = await service.suspend(
                    context,
                    membership_id=fixture.member_membership,
                    expected_version=2,
                    now=now,
                )
                assert (suspended.status, suspended.version) == (MembershipStatus.SUSPENDED, 3)
                active = await service.reactivate(
                    context,
                    membership_id=fixture.member_membership,
                    expected_version=3,
                    now=now,
                )
                assert (active.status, active.version) == (MembershipStatus.ACTIVE, 4)
                revoked = await service.revoke(
                    context,
                    membership_id=fixture.member_membership,
                    expected_version=4,
                    now=now,
                )
                assert (revoked.status, revoked.version) == (MembershipStatus.REVOKED, 5)

                pending = await service.revoke(
                    context,
                    membership_id=fixture.pending_membership,
                    expected_version=1,
                    now=now,
                )
                assert pending.status is MembershipStatus.REVOKED
                challenge = await session.get(ActivationChallenge, fixture.pending_challenge)
                assert challenge is not None and challenge.status == "REVOKED"

                retained = await session.get(WorkspaceMembership, fixture.member_membership)
                assert retained is not None and retained.status == "REVOKED"
                actions = (
                    await session.execute(
                        select(AuditEvent.action_code, AuditEvent.result_code).where(
                            AuditEvent.workspace_id == fixture.workspace_a
                        )
                    )
                ).all()
                assert ("MEMBER_ROLE_CHANGED", "SUCCEEDED") in actions
                assert ("MEMBER_SUSPENDED", "SUCCEEDED") in actions
                assert ("MEMBER_REACTIVATED", "SUCCEEDED") in actions
                assert ("MEMBER_REVOKED", "SUCCEEDED") in actions
                assert ("MEMBER_SUSPENDED", "DENIED") in actions
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
