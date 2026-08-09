"""PostgreSQL rotating-session, reuse, expiry, and logout integration tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import AuthSession
from app.infrastructure.database.repositories.bootstrap import SqlAlchemyBootstrapRepository
from app.infrastructure.database.repositories.sessions import SqlAlchemySessionRepository
from app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    transactional_session,
)
from app.modules.bootstrap import BootstrapCommand, BootstrapService, WorkspaceType
from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialService,
    PasswordDigest,
    SecretBytes,
    SecretText,
)
from app.modules.sessions import (
    LoginAttempt,
    LogoutAttempt,
    LogoutScope,
    RotationAttempt,
    SessionService,
    SessionTokens,
)


async def _clear(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, auth_sessions, activation_challenges, "
                    "workspace_modules, workspace_memberships, workspaces, user_accounts, "
                    "bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


async def _bootstrap(settings: Settings) -> tuple[str, str]:
    email = f"session-admin-{uuid4().hex}@example.invalid"
    password = "synthetic-session-password"
    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)
    try:
        async with transactional_session(sessions) as session:
            result = await BootstrapService(
                SqlAlchemyBootstrapRepository(session), Argon2idPasswordService()
            ).complete(
                BootstrapCommand(
                    display_name="Session Admin",
                    email=email,
                    password=SecretText(password),
                    account_language="en",
                    account_timezone="UTC",
                    workspace_name="Session Workspace",
                    workspace_type=WorkspaceType.HOUSEHOLD,
                    base_currency_code="USD",
                    workspace_language="en",
                    workspace_timezone="UTC",
                    correlation_id=uuid4(),
                )
            )
        return email, str(result.account_id)
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
    dummy: PasswordDigest,
) -> SessionService:
    return SessionService(
        SqlAlchemySessionRepository(session, credentials),
        credentials,
        passwords,
        dummy,
    )


async def _login(
    sessions: async_sessionmaker[AsyncSession],
    credentials: OpaqueCredentialService,
    passwords: Argon2idPasswordService,
    dummy: PasswordDigest,
    email: str,
    now: datetime,
) -> SessionTokens:
    async with transactional_session(sessions) as session:
        tokens = await _service(session, credentials, passwords, dummy).login(
            LoginAttempt(
                email,
                SecretText("synthetic-session-password"),
                uuid4(),
                now,
            )
        )
        assert tokens is not None
        return tokens


@pytest.mark.postgres
def test_login_rotation_and_reuse_revoke_the_complete_family(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        email, account_id = await _bootstrap(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        dummy = passwords.hash(SecretText("synthetic-dummy-password"))
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            tokens = await _login(sessions, credentials, passwords, dummy, email, now)

            async with transactional_session(sessions) as session:
                authenticated = await _service(session, credentials, passwords, dummy).authenticate(
                    tokens.access,
                    correlation_id=uuid4(),
                    now=now + timedelta(seconds=1),
                )
                assert authenticated is not None
                assert str(authenticated.account_id) == account_id

            async with transactional_session(sessions) as session:
                wrong_csrf = await _service(session, credentials, passwords, dummy).rotate(
                    RotationAttempt(
                        tokens.refresh,
                        SecretText("synthetic-wrong-csrf-value-not-persisted"),
                        uuid4(),
                        now + timedelta(seconds=30),
                    )
                )
                assert wrong_csrf is None

            async with transactional_session(sessions) as session:
                rotated = await _service(session, credentials, passwords, dummy).rotate(
                    RotationAttempt(
                        tokens.refresh,
                        tokens.csrf,
                        uuid4(),
                        now + timedelta(minutes=1),
                    )
                )
                assert rotated is not None

            async with transactional_session(sessions) as session:
                old_access = await _service(session, credentials, passwords, dummy).authenticate(
                    tokens.access,
                    correlation_id=uuid4(),
                    now=now + timedelta(minutes=2),
                )
                assert old_access is None

            async with transactional_session(sessions) as session:
                replay = await _service(session, credentials, passwords, dummy).rotate(
                    RotationAttempt(
                        tokens.refresh,
                        tokens.csrf,
                        uuid4(),
                        now + timedelta(minutes=2),
                    )
                )
                assert replay is None

            async with transactional_session(sessions) as session:
                newest_access = await _service(session, credentials, passwords, dummy).authenticate(
                    rotated.access,
                    correlation_id=uuid4(),
                    now=now + timedelta(minutes=3),
                )
                assert newest_access is None

            async with sessions() as session:
                rows = (
                    await session.scalars(
                        select(AuthSession).order_by(AuthSession.issued_at, AuthSession.id)
                    )
                ).all()
                assert [row.status for row in rows] == ["REUSE_DETECTED", "REVOKED"]
                assert len({row.family_id for row in rows}) == 1
                assert all(
                    value
                    not in {
                        row.access_credential_digest,
                        row.refresh_credential_digest,
                        row.csrf_credential_digest,
                    }
                    for row in rows
                    for value in (
                        tokens.access.reveal(),
                        tokens.refresh.reveal(),
                        tokens.csrf.reveal(),
                    )
                )
                actions = set(
                    await session.scalars(
                        select(AuditEvent.action_code).where(
                            AuditEvent.action_code.in_(
                                (
                                    "LOGIN_SUCCEEDED",
                                    "SESSION_CREATED",
                                    "SESSION_ROTATED",
                                    "SESSION_REUSE_DETECTED",
                                )
                            )
                        )
                    )
                )
                assert actions == {
                    "LOGIN_SUCCEEDED",
                    "SESSION_CREATED",
                    "SESSION_ROTATED",
                    "SESSION_REUSE_DETECTED",
                }
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_concurrent_zero_grace_refresh_has_one_rotation_then_revokes_family(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        email, _ = await _bootstrap(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        dummy = passwords.hash(SecretText("synthetic-dummy-password"))
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            tokens = await _login(sessions, credentials, passwords, dummy, email, now)

            async def rotate() -> SessionTokens | None:
                async with transactional_session(sessions) as session:
                    return await _service(session, credentials, passwords, dummy).rotate(
                        RotationAttempt(
                            tokens.refresh,
                            tokens.csrf,
                            uuid4(),
                            now + timedelta(minutes=1),
                        )
                    )

            outcomes = await asyncio.gather(rotate(), rotate())
            assert sum(outcome is not None for outcome in outcomes) == 1
            async with sessions() as session:
                statuses = list(await session.scalars(select(AuthSession.status)))
                assert sorted(statuses) == ["REUSE_DETECTED", "REVOKED"]
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_expiry_account_state_and_logout_scopes_remove_intended_access(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        email, account_id_text = await _bootstrap(migrated_database)
        account_id = UUID(account_id_text)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        passwords = Argon2idPasswordService()
        dummy = passwords.hash(SecretText("synthetic-dummy-password"))
        now = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            expired = await _login(sessions, credentials, passwords, dummy, email, now)
            async with transactional_session(sessions) as session:
                outcome = await _service(session, credentials, passwords, dummy).rotate(
                    RotationAttempt(
                        expired.refresh,
                        expired.csrf,
                        uuid4(),
                        now + timedelta(days=7),
                    )
                )
                assert outcome is None

            first = await _login(
                sessions, credentials, passwords, dummy, email, now + timedelta(hours=2)
            )
            second = await _login(
                sessions,
                credentials,
                passwords,
                dummy,
                email,
                now + timedelta(hours=2, minutes=1),
            )
            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, dummy).logout(
                    LogoutAttempt(
                        first.refresh,
                        first.csrf,
                        LogoutScope.CURRENT,
                        uuid4(),
                        now + timedelta(hours=2, minutes=2),
                    )
                )
            async with transactional_session(sessions) as session:
                assert (
                    await _service(session, credentials, passwords, dummy).authenticate(
                        first.access,
                        correlation_id=uuid4(),
                        now=now + timedelta(hours=2, minutes=3),
                    )
                    is None
                )
                assert (
                    await _service(session, credentials, passwords, dummy).authenticate(
                        second.access,
                        correlation_id=uuid4(),
                        now=now + timedelta(hours=2, minutes=3),
                    )
                    is not None
                )

            async with transactional_session(sessions) as session:
                await _service(session, credentials, passwords, dummy).logout(
                    LogoutAttempt(
                        second.refresh,
                        second.csrf,
                        LogoutScope.ALL,
                        uuid4(),
                        now + timedelta(hours=2, minutes=4),
                    )
                )
            async with transactional_session(sessions) as session:
                assert (
                    await _service(session, credentials, passwords, dummy).authenticate(
                        second.access,
                        correlation_id=uuid4(),
                        now=now + timedelta(hours=2, minutes=5),
                    )
                    is None
                )

            active = await _login(
                sessions, credentials, passwords, dummy, email, now + timedelta(hours=3)
            )
            async with transactional_session(sessions) as session:
                account = await session.get(UserAccount, account_id, with_for_update=True)
                assert account is not None
                account.status = "SUSPENDED"
            async with transactional_session(sessions) as session:
                assert (
                    await _service(session, credentials, passwords, dummy).authenticate(
                        active.access,
                        correlation_id=uuid4(),
                        now=now + timedelta(hours=3, minutes=5),
                    )
                    is None
                )

            async with sessions() as session:
                active_count = await session.scalar(
                    select(func.count())
                    .select_from(AuthSession)
                    .where(AuthSession.status == "ACTIVE")
                )
                expired_count = await session.scalar(
                    select(func.count())
                    .select_from(AuthSession)
                    .where(AuthSession.status == "EXPIRED")
                )
                revoked_audits = await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action_code == "SESSION_REVOKED")
                )
                assert active_count == 0
                assert expired_count == 1
                assert revoked_audits == 3
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
