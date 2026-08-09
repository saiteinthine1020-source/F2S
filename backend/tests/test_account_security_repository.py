"""PostgreSQL password-change and concealed recovery lifecycle tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import AuthSession, RecoveryChallenge
from app.infrastructure.database.repositories.account_security import (
    SqlAlchemyAccountSecurityRepository,
)
from app.infrastructure.database.repositories.bootstrap import SqlAlchemyBootstrapRepository
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.account_security import (
    AccountSecurityService,
    DevelopmentRecoveryOutbox,
    PasswordChangeAttempt,
    RecoveryConfirmation,
    RecoveryRequest,
)
from app.modules.bootstrap import BootstrapCommand, BootstrapService, WorkspaceType
from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretBytes,
    SecretText,
)


async def _clear(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, recovery_challenges, auth_sessions, "
                    "activation_challenges, workspace_modules, workspace_memberships, "
                    "workspaces, user_accounts, bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


def _credentials(settings: Settings) -> OpaqueCredentialService:
    return OpaqueCredentialService(
        KeyedDigestService(
            SecretBytes(settings.identity_digest_key.get_secret_value().encode("utf-8"))
        )
    )


def _service(
    session: AsyncSession,
    credentials: OpaqueCredentialService,
    passwords: Argon2idPasswordService,
    outbox: DevelopmentRecoveryOutbox | None = None,
) -> AccountSecurityService:
    return AccountSecurityService(
        SqlAlchemyAccountSecurityRepository(session, credentials),
        credentials,
        passwords,
        outbox or DevelopmentRecoveryOutbox(),
    )


async def _create_account(
    sessions: async_sessionmaker[AsyncSession],
    passwords: Argon2idPasswordService,
) -> tuple[UUID, str]:
    account_id = uuid4()
    email = f"recovery-{uuid4().hex}@example.invalid"
    async with transactional_session(sessions) as session:
        session.add(
            UserAccount(
                id=account_id,
                normalized_email=email,
                display_name="Recovery Member",
                password_digest=passwords.hash(
                    SecretText("synthetic-current-password")
                ).for_persistence(),
                status="ACTIVE",
                preferred_language="en",
                timezone="UTC",
            )
        )
    return account_id, email


async def _add_session(
    sessions: async_sessionmaker[AsyncSession],
    credentials: OpaqueCredentialService,
    account_id: UUID,
    now: datetime,
) -> UUID:
    access = credentials.issue(
        OpaqueCredentialPurpose.ACCESS_CREDENTIAL,
        now=now,
        lifetime=timedelta(minutes=15),
    )
    refresh = credentials.issue(
        OpaqueCredentialPurpose.REFRESH_CREDENTIAL,
        now=now,
        lifetime=timedelta(days=7),
    )
    csrf = credentials.issue(
        OpaqueCredentialPurpose.CSRF_CREDENTIAL,
        now=now,
        lifetime=timedelta(days=7),
    )
    session_id = uuid4()
    async with transactional_session(sessions) as session:
        session.add(
            AuthSession(
                id=session_id,
                user_account_id=account_id,
                family_id=uuid4(),
                access_credential_digest=access.record.digest.for_persistence(),
                refresh_credential_digest=refresh.record.digest.for_persistence(),
                csrf_credential_digest=csrf.record.digest.for_persistence(),
                digest_algorithm_code="SHA256",
                status="ACTIVE",
                issued_at=now,
                access_expires_at=access.record.expires_at,
                refresh_idle_expires_at=refresh.record.expires_at,
                absolute_expires_at=now + timedelta(days=30),
            )
        )
    return session_id


@pytest.mark.postgres
def test_password_change_reauthenticates_and_revokes_only_other_sessions(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            account_id, _ = await _create_account(sessions, passwords)
            current_id = await _add_session(sessions, credentials, account_id, now)
            other_id = await _add_session(sessions, credentials, account_id, now)
            async with transactional_session(sessions) as session:
                denied = await _service(session, credentials, passwords).change_password(
                    PasswordChangeAttempt(
                        account_id,
                        current_id,
                        SecretText("synthetic-wrong-password"),
                        SecretText("synthetic-replacement-password"),
                        uuid4(),
                        now + timedelta(minutes=1),
                    )
                )
                assert denied is False
            async with transactional_session(sessions) as session:
                changed = await _service(session, credentials, passwords).change_password(
                    PasswordChangeAttempt(
                        account_id,
                        current_id,
                        SecretText("synthetic-current-password"),
                        SecretText("synthetic-replacement-password"),
                        uuid4(),
                        now + timedelta(minutes=2),
                    )
                )
                assert changed is True
            async with sessions() as session:
                account = await session.get(UserAccount, account_id)
                current = await session.get(AuthSession, current_id)
                other = await session.get(AuthSession, other_id)
                assert account is not None and account.password_digest is not None
                assert current is not None and current.status == "ACTIVE"
                assert other is not None and other.status == "REVOKED"
                assert other.revoke_reason_code == "PASSWORD_CHANGED"
                assert not passwords.verify(
                    SecretText("synthetic-current-password"),
                    PasswordDigest(account.password_digest),
                ).matches
                assert passwords.verify(
                    SecretText("synthetic-replacement-password"),
                    PasswordDigest(account.password_digest),
                ).matches
                changed_audits = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action_code == "PASSWORD_CHANGED")
                )
                assert changed_audits == 2
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_recovery_is_single_use_concurrent_and_revokes_all_sessions(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            account_id, email = await _create_account(sessions, passwords)
            await _add_session(sessions, credentials, account_id, now)
            await _add_session(sessions, credentials, account_id, now)
            outbox = DevelopmentRecoveryOutbox()
            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest(email, uuid4(), now)
                )
            delivery = outbox.drain()
            assert len(delivery) == 1
            raw_value = delivery[0].value.reveal()

            async def complete() -> bool:
                async with transactional_session(sessions) as session:
                    return await _service(session, credentials, passwords).confirm_recovery(
                        RecoveryConfirmation(
                            delivery[0].value,
                            SecretText("synthetic-recovered-password"),
                            uuid4(),
                            now + timedelta(minutes=1),
                        )
                    )

            outcomes = await asyncio.gather(complete(), complete())
            assert sorted(outcomes) == [False, True]
            async with transactional_session(sessions) as session:
                replay = await _service(session, credentials, passwords).confirm_recovery(
                    RecoveryConfirmation(
                        delivery[0].value,
                        SecretText("synthetic-another-password"),
                        uuid4(),
                        now + timedelta(minutes=2),
                    )
                )
                assert replay is False
            async with sessions() as session:
                account = await session.get(UserAccount, account_id)
                challenges = (
                    await session.scalars(
                        select(RecoveryChallenge).where(
                            RecoveryChallenge.user_account_id == account_id
                        )
                    )
                ).all()
                active_sessions = await session.scalar(
                    select(func.count())
                    .select_from(AuthSession)
                    .where(AuthSession.status == "ACTIVE")
                )
                assert account is not None and account.password_digest is not None
                assert passwords.verify(
                    SecretText("synthetic-recovered-password"),
                    PasswordDigest(account.password_digest),
                ).matches
                assert active_sessions == 0
                assert len(challenges) == 1 and challenges[0].status == "USED"
                assert challenges[0].attempt_count == 3
                assert raw_value not in challenges[0].challenge_digest
                completed_audits = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action_code == "RECOVERY_COMPLETED")
                )
                assert completed_audits == 3
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_recovery_expiry_restart_and_missing_account_are_concealed(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        now = datetime(2026, 8, 9, tzinfo=UTC)
        outbox = DevelopmentRecoveryOutbox()
        try:
            _, email = await _create_account(sessions, passwords)
            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest("missing@example.invalid", uuid4(), now)
                )
            assert outbox.drain() == ()

            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest(email, uuid4(), now)
                )
            expired_delivery = outbox.drain()[0]
            async with transactional_session(sessions) as session:
                expired = await _service(session, credentials, passwords).confirm_recovery(
                    RecoveryConfirmation(
                        expired_delivery.value,
                        SecretText("synthetic-expired-password"),
                        uuid4(),
                        now + timedelta(hours=24),
                    )
                )
                assert expired is False

            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest(email, uuid4(), now + timedelta(days=2))
                )
            revoked_delivery = outbox.drain()[0]
            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest(email, uuid4(), now + timedelta(days=2, minutes=1))
                )
            outbox.drain()
            async with transactional_session(sessions) as session:
                revoked = await _service(session, credentials, passwords).confirm_recovery(
                    RecoveryConfirmation(
                        revoked_delivery.value,
                        SecretText("synthetic-revoked-password"),
                        uuid4(),
                        now + timedelta(days=2, minutes=2),
                    )
                )
                assert revoked is False
            async with sessions() as session:
                statuses = (
                    await session.scalars(
                        select(RecoveryChallenge.status).order_by(RecoveryChallenge.issued_at)
                    )
                ).all()
                assert statuses == ["EXPIRED", "REVOKED", "ISSUED"]
                requests = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action_code == "RECOVERY_REQUESTED")
                )
                assert requests == 4
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_ordinary_recovery_does_not_bypass_owner_recovery_boundary(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        outbox = DevelopmentRecoveryOutbox()
        email = f"owner-recovery-{uuid4().hex}@example.invalid"
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            async with transactional_session(sessions) as session:
                await BootstrapService(SqlAlchemyBootstrapRepository(session), passwords).complete(
                    BootstrapCommand(
                        display_name="Workspace Owner",
                        email=email,
                        password=SecretText("synthetic-owner-password"),
                        account_language="en",
                        account_timezone="UTC",
                        workspace_name="Owner Workspace",
                        workspace_type=WorkspaceType.HOUSEHOLD,
                        base_currency_code="USD",
                        workspace_language="en",
                        workspace_timezone="UTC",
                        correlation_id=uuid4(),
                    )
                )
            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, outbox).request_recovery(
                    RecoveryRequest(email, uuid4(), now)
                )
            assert outbox.drain() == ()
            async with sessions() as session:
                challenge_count = await session.scalar(
                    select(func.count()).select_from(RecoveryChallenge)
                )
                requested_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action_code == "RECOVERY_REQUESTED")
                )
                assert challenge_count == 0
                assert requested_count == 1
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
