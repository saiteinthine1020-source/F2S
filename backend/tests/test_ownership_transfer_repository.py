"""PostgreSQL ownership-transfer atomicity, isolation, and concurrency tests."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity_security import AuthSession
from app.infrastructure.database.models.workspace_access import (
    OwnershipTransfer,
    Workspace,
    WorkspaceMembership,
)
from app.infrastructure.database.repositories.ownership_transfer import (
    SqlAlchemyOwnershipTransferRepository,
)
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialService,
    SecretBytes,
    SecretText,
)
from app.modules.ownership_transfer import (
    CancelOwnershipTransfer,
    ConfirmOwnershipTransfer,
    DevelopmentOwnershipOutbox,
    InitiateOwnershipTransfer,
    OwnershipNotificationUnavailable,
    OwnershipTransferConfirmationDenied,
    OwnershipTransferService,
    OwnershipTransferStatus,
    RejectingOwnershipNotifications,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)

NOW = datetime(2026, 8, 9, 14, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Fixture:
    workspace: UUID
    owner_account: UUID
    owner_membership: UUID
    owner_session: UUID
    target_account: UUID
    target_membership: UUID
    target_session: UUID
    foreign_membership: UUID


def _credentials() -> OpaqueCredentialService:
    return OpaqueCredentialService(
        KeyedDigestService(SecretBytes(b"synthetic-transfer-repository-key-material"))
    )


async def _clear(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, ownership_transfers, recovery_challenges, "
                    "activation_challenges, auth_sessions, workspace_modules, "
                    "workspace_memberships, workspaces, user_accounts, bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


async def _seed(settings: Settings, password_digest: str) -> Fixture:
    values = [uuid4() for _ in range(8)]
    fixture = Fixture(*values)
    foreign_workspace, foreign_owner_account, foreign_owner_membership = (
        uuid4(),
        uuid4(),
        uuid4(),
    )
    suffix = uuid4().hex
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO user_accounts "
                    "(id, normalized_email, display_name, password_digest, status, "
                    "preferred_language, timezone) VALUES "
                    "(:owner, :owner_email, 'Owner', :password, 'ACTIVE', 'en', 'UTC'), "
                    "(:target, :target_email, 'Target', :password, 'ACTIVE', 'en', 'UTC'), "
                    "(:foreign_owner, :foreign_owner_email, 'Foreign Owner', :password, "
                    "'ACTIVE', 'en', 'UTC'), (:foreign, :foreign_email, 'Foreign Member', "
                    ":password, 'ACTIVE', 'en', 'UTC')"
                ),
                {
                    "owner": fixture.owner_account,
                    "owner_email": f"owner-{suffix}@example.invalid",
                    "target": fixture.target_account,
                    "target_email": f"target-{suffix}@example.invalid",
                    "foreign_owner": foreign_owner_account,
                    "foreign_owner_email": f"foreign-owner-{suffix}@example.invalid",
                    "foreign": uuid4(),
                    "foreign_email": f"foreign-{suffix}@example.invalid",
                    "password": password_digest,
                },
            )
            foreign_account = await connection.scalar(
                text("SELECT id FROM user_accounts WHERE normalized_email = :email"),
                {"email": f"foreign-{suffix}@example.invalid"},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "owner_membership_id, owner_role, owner_membership_status, status) VALUES "
                    "(:workspace, 'Workspace', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    ":owner_membership, 'ADMIN', 'ACTIVE', 'ACTIVE'), "
                    "(:foreign_workspace, 'Foreign', 'FARM', 'JPY', 'UTC', 'en', "
                    ":foreign_owner_membership, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {
                    "workspace": fixture.workspace,
                    "owner_membership": fixture.owner_membership,
                    "foreign_workspace": foreign_workspace,
                    "foreign_owner_membership": foreign_owner_membership,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id, workspace_id, user_account_id, role, status) VALUES "
                    "(:owner_membership, :workspace, :owner, 'ADMIN', 'ACTIVE'), "
                    "(:target_membership, :workspace, :target, 'CONTRIBUTOR', 'ACTIVE'), "
                    "(:foreign_owner_membership, :foreign_workspace, :foreign_owner, "
                    "'ADMIN', 'ACTIVE'), (:foreign_membership, :foreign_workspace, "
                    ":foreign, 'ADVISOR', 'ACTIVE')"
                ),
                {
                    "owner_membership": fixture.owner_membership,
                    "workspace": fixture.workspace,
                    "owner": fixture.owner_account,
                    "target_membership": fixture.target_membership,
                    "target": fixture.target_account,
                    "foreign_owner_membership": foreign_owner_membership,
                    "foreign_workspace": foreign_workspace,
                    "foreign_owner": foreign_owner_account,
                    "foreign_membership": fixture.foreign_membership,
                    "foreign": foreign_account,
                },
            )
            for session_id, account, prefix in (
                (fixture.owner_session, fixture.owner_account, "owner"),
                (fixture.target_session, fixture.target_account, "target"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO auth_sessions "
                        "(id, user_account_id, family_id, access_credential_digest, "
                        "refresh_credential_digest, csrf_credential_digest, status, issued_at, "
                        "access_expires_at, refresh_idle_expires_at, absolute_expires_at) "
                        "VALUES (:id, :account, :family, :access, :refresh, :csrf, 'ACTIVE', "
                        "current_timestamp, current_timestamp + interval '15 minutes', "
                        "current_timestamp + interval '1 day', "
                        "current_timestamp + interval '30 days')"
                    ),
                    {
                        "id": session_id,
                        "account": account,
                        "family": uuid4(),
                        "access": f"{prefix}-access-{suffix}",
                        "refresh": f"{prefix}-refresh-{suffix}",
                        "csrf": f"{prefix}-csrf-{suffix}",
                    },
                )
    finally:
        await engine.dispose()
    return fixture


def _owner_context(fixture: Fixture) -> AuthorizationContext:
    return AuthorizationContext(
        fixture.owner_account,
        fixture.workspace,
        fixture.owner_membership,
        WorkspaceRole.ADMIN,
        uuid4(),
    )


def _target_context(fixture: Fixture) -> AuthorizationContext:
    return AuthorizationContext(
        fixture.target_account,
        fixture.workspace,
        fixture.target_membership,
        WorkspaceRole.CONTRIBUTOR,
        uuid4(),
    )


async def _initiate(
    settings: Settings,
    fixture: Fixture,
    passwords: Argon2idPasswordService,
    credentials: OpaqueCredentialService,
    *,
    now: datetime = NOW,
) -> tuple[UUID, SecretText]:
    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)
    outbox = DevelopmentOwnershipOutbox()
    try:
        async with transactional_session(sessions) as session:
            service = OwnershipTransferService(
                SqlAlchemyOwnershipTransferRepository(session, credentials),
                credentials,
                passwords,
                outbox,
            )
            transfer = await service.initiate(
                InitiateOwnershipTransfer(
                    _owner_context(fixture),
                    fixture.owner_session,
                    fixture.target_membership,
                    WorkspaceRole.ADVISOR,
                    SecretText("synthetic-current-password"),
                    now,
                )
            )
        intent = outbox.drain()[0][0]
        assert intent.value is not None
        return transfer.id, intent.value
    finally:
        await engine.dispose()


@pytest.mark.postgres
def test_transfer_is_atomic_revokes_sessions_audits_and_denies_replay(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        passwords = Argon2idPasswordService()
        password_digest = passwords.hash(SecretText("synthetic-current-password")).for_persistence()
        fixture = await _seed(migrated_database, password_digest)
        credentials = _credentials()
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            async with transactional_session(sessions) as session:
                service = OwnershipTransferService(
                    SqlAlchemyOwnershipTransferRepository(session, credentials),
                    credentials,
                    passwords,
                    DevelopmentOwnershipOutbox(),
                )
                with pytest.raises(AuthorizationDenied):
                    await service.initiate(
                        InitiateOwnershipTransfer(
                            _owner_context(fixture),
                            fixture.owner_session,
                            fixture.foreign_membership,
                            WorkspaceRole.CONTRIBUTOR,
                            SecretText("synthetic-current-password"),
                            NOW,
                        )
                    )

                target = await session.get(WorkspaceMembership, fixture.target_membership)
                assert target is not None
                target.status = "SUSPENDED"
                await session.flush()
                with pytest.raises(AuthorizationDenied):
                    await service.initiate(
                        InitiateOwnershipTransfer(
                            _owner_context(fixture),
                            fixture.owner_session,
                            fixture.target_membership,
                            WorkspaceRole.CONTRIBUTOR,
                            SecretText("synthetic-current-password"),
                            NOW,
                        )
                    )
                target.status = "ACTIVE"
                await session.flush()

            cancelled_id, _ = await _initiate(migrated_database, fixture, passwords, credentials)
            async with transactional_session(sessions) as session:
                await OwnershipTransferService(
                    SqlAlchemyOwnershipTransferRepository(session, credentials),
                    credentials,
                    passwords,
                    DevelopmentOwnershipOutbox(),
                ).cancel(CancelOwnershipTransfer(_owner_context(fixture), cancelled_id, 1, NOW))
            async with transactional_session(sessions) as session:
                cancelled = await session.get(OwnershipTransfer, cancelled_id)
                assert cancelled is not None and cancelled.status == "CANCELLED"

            expired_id, expired_value = await _initiate(
                migrated_database, fixture, passwords, credentials
            )
            async with transactional_session(sessions) as session:
                with pytest.raises(OwnershipTransferConfirmationDenied):
                    await OwnershipTransferService(
                        SqlAlchemyOwnershipTransferRepository(session, credentials),
                        credentials,
                        passwords,
                        DevelopmentOwnershipOutbox(),
                    ).confirm(
                        ConfirmOwnershipTransfer(
                            _target_context(fixture),
                            expired_id,
                            expired_value,
                            NOW.replace(hour=15),
                        )
                    )
            async with transactional_session(sessions) as session:
                expired = await session.get(OwnershipTransfer, expired_id)
                assert expired is not None and expired.status == "EXPIRED"

            transfer_id, value = await _initiate(
                migrated_database,
                fixture,
                passwords,
                credentials,
                now=NOW.replace(hour=15, minute=1),
            )
            outbox = DevelopmentOwnershipOutbox()
            async with transactional_session(sessions) as session:
                completed = await OwnershipTransferService(
                    SqlAlchemyOwnershipTransferRepository(session, credentials),
                    credentials,
                    passwords,
                    outbox,
                ).confirm(
                    ConfirmOwnershipTransfer(
                        _target_context(fixture),
                        transfer_id,
                        value,
                        NOW.replace(hour=15, minute=1),
                    )
                )
                assert completed.status is OwnershipTransferStatus.COMPLETED

            async with transactional_session(sessions) as session:
                workspace = await session.get(Workspace, fixture.workspace)
                owner = await session.get(WorkspaceMembership, fixture.owner_membership)
                target = await session.get(WorkspaceMembership, fixture.target_membership)
                assert (
                    workspace is not None
                    and workspace.owner_membership_id == fixture.target_membership
                )
                assert owner is not None and (owner.role, owner.status) == ("ADVISOR", "ACTIVE")
                assert target is not None and (target.role, target.status) == ("ADMIN", "ACTIVE")
                count = await session.scalar(
                    select(func.count())
                    .select_from(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == fixture.workspace,
                        WorkspaceMembership.role == "ADMIN",
                        WorkspaceMembership.status == "ACTIVE",
                    )
                )
                assert count == 1
                assert (await session.get(AuthSession, fixture.owner_session)).status == "REVOKED"  # type: ignore[union-attr]
                assert (await session.get(AuthSession, fixture.target_session)).status == "REVOKED"  # type: ignore[union-attr]
                actions = set(
                    (
                        await session.scalars(
                            select(AuditEvent.action_code).where(
                                AuditEvent.workspace_id == fixture.workspace
                            )
                        )
                    ).all()
                )
                assert {
                    "OWNERSHIP_TRANSFER_INITIATED",
                    "OWNERSHIP_TRANSFER_CONFIRMED",
                    "OWNERSHIP_TRANSFER_COMPLETED",
                    "SESSION_REVOKED",
                } <= actions
            assert len(outbox.drain()[0]) == 2

            async with transactional_session(sessions) as session:
                with pytest.raises(OwnershipTransferConfirmationDenied):
                    await OwnershipTransferService(
                        SqlAlchemyOwnershipTransferRepository(session, credentials),
                        credentials,
                        passwords,
                        DevelopmentOwnershipOutbox(),
                    ).confirm(
                        ConfirmOwnershipTransfer(
                            _target_context(fixture),
                            transfer_id,
                            value,
                            NOW.replace(hour=15, minute=1),
                        )
                    )
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_notification_failure_rolls_back_and_concurrent_confirmation_has_one_winner(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        passwords = Argon2idPasswordService()
        password_digest = passwords.hash(SecretText("synthetic-current-password")).for_persistence()
        fixture = await _seed(migrated_database, password_digest)
        credentials = _credentials()
        transfer_id, value = await _initiate(migrated_database, fixture, passwords, credentials)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        try:
            with pytest.raises(OwnershipNotificationUnavailable):
                async with transactional_session(sessions) as session:
                    await OwnershipTransferService(
                        SqlAlchemyOwnershipTransferRepository(session, credentials),
                        credentials,
                        passwords,
                        RejectingOwnershipNotifications(),
                    ).confirm(
                        ConfirmOwnershipTransfer(_target_context(fixture), transfer_id, value, NOW)
                    )
            async with transactional_session(sessions) as session:
                workspace = await session.get(Workspace, fixture.workspace)
                transfer = await session.get(OwnershipTransfer, transfer_id)
                owner = await session.get(WorkspaceMembership, fixture.owner_membership)
                target = await session.get(WorkspaceMembership, fixture.target_membership)
                assert (
                    workspace is not None
                    and workspace.owner_membership_id == fixture.owner_membership
                )
                assert transfer is not None and transfer.status == "INITIATED"
                assert owner is not None and owner.role == "ADMIN"
                assert target is not None and target.role == "CONTRIBUTOR"

            async def compete() -> bool:
                async with transactional_session(sessions) as session:
                    try:
                        await OwnershipTransferService(
                            SqlAlchemyOwnershipTransferRepository(session, credentials),
                            credentials,
                            passwords,
                            DevelopmentOwnershipOutbox(),
                        ).confirm(
                            ConfirmOwnershipTransfer(
                                _target_context(fixture), transfer_id, value, NOW
                            )
                        )
                    except OwnershipTransferConfirmationDenied:
                        return False
                    return True

            assert sorted(await asyncio.gather(compete(), compete())) == [False, True]
            async with transactional_session(sessions) as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == fixture.workspace,
                        WorkspaceMembership.role == "ADMIN",
                        WorkspaceMembership.status == "ACTIVE",
                    )
                )
                assert count == 1
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
