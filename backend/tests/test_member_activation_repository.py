"""PostgreSQL member provisioning and single-use activation lifecycle tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.infrastructure.database.models.audit import AuditEvent
from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import ActivationChallenge
from app.infrastructure.database.models.workspace_access import WorkspaceMembership
from app.infrastructure.database.repositories.bootstrap import SqlAlchemyBootstrapRepository
from app.infrastructure.database.repositories.member_activation import (
    SqlAlchemyMemberActivationRepository,
)
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
from app.modules.member_activation import (
    ActivationAttempt,
    DevelopmentActivationOutbox,
    DuplicateMembership,
    MemberActivationService,
    MemberRole,
    ProvisionedMember,
    ProvisionMemberCommand,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)


def _credentials(settings: Settings) -> OpaqueCredentialService:
    return OpaqueCredentialService(
        KeyedDigestService(
            SecretBytes(settings.identity_digest_key.get_secret_value().encode("utf-8"))
        )
    )


async def _clear(settings: Settings) -> None:
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE audit_events, activation_challenges, workspace_modules, "
                    "workspace_memberships, workspaces, user_accounts, bootstrap_state CASCADE"
                )
            )
    finally:
        await engine.dispose()


async def _bootstrap(settings: Settings) -> AuthorizationContext:
    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)
    correlation_id = uuid4()
    try:
        async with transactional_session(sessions) as session:
            result = await BootstrapService(
                SqlAlchemyBootstrapRepository(session),
                Argon2idPasswordService(),
            ).complete(
                BootstrapCommand(
                    display_name="Activation Admin",
                    email=f"activation-admin-{uuid4().hex}@example.invalid",
                    password=SecretText("synthetic-admin-password"),
                    account_language="en",
                    account_timezone="UTC",
                    workspace_name="Activation Workspace",
                    workspace_type=WorkspaceType.FARM,
                    base_currency_code="USD",
                    workspace_language="en",
                    workspace_timezone="UTC",
                    correlation_id=correlation_id,
                )
            )
        return AuthorizationContext(
            actor_account_id=result.account_id,
            workspace_id=result.workspace_id,
            membership_id=result.membership_id,
            role=WorkspaceRole.ADMIN,
            correlation_id=correlation_id,
        )
    finally:
        await engine.dispose()


def _command(context: AuthorizationContext, email: str) -> ProvisionMemberCommand:
    return ProvisionMemberCommand(
        context=context,
        email=email,
        display_name="Provisioned Member",
        role=MemberRole.CONTRIBUTOR,
        preferred_language="en",
        timezone="UTC",
    )


@pytest.mark.postgres
def test_restart_revokes_old_challenge_and_only_newest_activates_once(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        context = await _bootstrap(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        delivery = DevelopmentActivationOutbox()
        issued_at = datetime(2026, 8, 9, tzinfo=UTC)
        try:
            async with transactional_session(sessions) as session:
                service = MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                )
                member = await service.provision(
                    _command(context, "new-member@example.invalid"), now=issued_at
                )
            first = delivery.drain()[0]

            async with transactional_session(sessions) as session:
                service = MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                )
                await service.restart(
                    context,
                    member.membership_id,
                    now=issued_at + timedelta(hours=1),
                )
            newest = delivery.drain()[0]

            async with transactional_session(sessions) as session:
                service = MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                )
                old = await service.activate(
                    ActivationAttempt(
                        first.value,
                        SecretText("synthetic-first-password"),
                        uuid4(),
                        issued_at + timedelta(hours=2),
                    )
                )
                assert not old.activated

            activation_id = uuid4()
            async with transactional_session(sessions) as session:
                service = MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                )
                activated = await service.activate(
                    ActivationAttempt(
                        newest.value,
                        SecretText("synthetic-first-password"),
                        activation_id,
                        issued_at + timedelta(hours=2),
                    )
                )
                assert activated.activated

            async with transactional_session(sessions) as session:
                replayed = await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                ).activate(
                    ActivationAttempt(
                        newest.value,
                        None,
                        uuid4(),
                        issued_at + timedelta(hours=3),
                    )
                )
                assert not replayed.activated

            async with sessions() as session:
                membership = await session.get(WorkspaceMembership, member.membership_id)
                assert membership is not None
                account = await session.get(UserAccount, membership.user_account_id)
                challenges = (
                    await session.scalars(
                        select(ActivationChallenge)
                        .where(ActivationChallenge.membership_id == member.membership_id)
                        .order_by(ActivationChallenge.issued_at)
                    )
                ).all()
                actions = (
                    await session.scalars(
                        select(AuditEvent.action_code).where(
                            AuditEvent.workspace_id == context.workspace_id
                        )
                    )
                ).all()
                assert account is not None and account.status == "ACTIVE"
                assert account.password_digest is not None
                assert (
                    Argon2idPasswordService()
                    .verify(
                        SecretText("synthetic-first-password"),
                        PasswordDigest(account.password_digest),
                    )
                    .matches
                )
                assert (membership.role, membership.status) == ("CONTRIBUTOR", "ACTIVE")
                assert [challenge.status for challenge in challenges] == ["REVOKED", "USED"]
                assert challenges[0].revoke_reason_code == "RESTARTED"
                assert {"MEMBER_CREATED", "ACTIVATION_RESTARTED", "MEMBER_ACTIVATED"} <= set(
                    actions
                )
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())


@pytest.mark.postgres
def test_duplicate_concurrency_expiry_and_wrong_workspace_are_safe(
    migrated_database: Settings,
) -> None:
    async def exercise() -> None:
        await _clear(migrated_database)
        context = await _bootstrap(migrated_database)
        engine = create_database_engine(migrated_database)
        sessions = create_session_factory(engine)
        credentials = _credentials(migrated_database)
        now = datetime(2026, 8, 9, tzinfo=UTC)

        async def provision() -> ProvisionedMember:
            async with transactional_session(sessions) as session:
                return await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    DevelopmentActivationOutbox(),
                ).provision(_command(context, "same-member@example.invalid"), now=now)

        try:
            existing_account_id = uuid4()
            existing_password = Argon2idPasswordService().hash(
                SecretText("synthetic-existing-password")
            )
            async with transactional_session(sessions) as session:
                session.add(
                    UserAccount(
                        id=existing_account_id,
                        normalized_email="existing-member@example.invalid",
                        display_name="Existing Account",
                        password_digest=existing_password.for_persistence(),
                        status="ACTIVE",
                        preferred_language="ja",
                        timezone="Asia/Tokyo",
                    )
                )

            existing_delivery = DevelopmentActivationOutbox()
            async with transactional_session(sessions) as session:
                existing_member = await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    existing_delivery,
                ).provision(_command(context, "EXISTING-MEMBER@example.invalid"), now=now)
            existing_value = existing_delivery.drain()[0].value
            async with transactional_session(sessions) as session:
                existing_outcome = await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    existing_delivery,
                ).activate(
                    ActivationAttempt(existing_value, None, uuid4(), now + timedelta(hours=1))
                )
                assert existing_outcome.activated

            async with sessions() as session:
                reused = await session.get(UserAccount, existing_account_id)
                reused_membership = await session.get(
                    WorkspaceMembership, existing_member.membership_id
                )
                assert reused is not None
                assert reused.display_name == "Existing Account"
                assert reused.password_digest == existing_password.for_persistence()
                assert reused_membership is not None
                assert reused_membership.user_account_id == existing_account_id
                assert reused_membership.status == "ACTIVE"

            outcomes = await asyncio.gather(provision(), provision(), return_exceptions=True)
            assert sum(not isinstance(item, Exception) for item in outcomes) == 1
            assert sum(isinstance(item, DuplicateMembership) for item in outcomes) == 1

            winner = cast(
                ProvisionedMember,
                next(item for item in outcomes if not isinstance(item, Exception)),
            )
            membership_id: UUID = winner.membership_id

            with pytest.raises(AuthorizationDenied):
                async with transactional_session(sessions) as session:
                    await MemberActivationService(
                        SqlAlchemyMemberActivationRepository(session, credentials),
                        credentials,
                        Argon2idPasswordService(),
                        DevelopmentActivationOutbox(),
                    ).restart(
                        AuthorizationContext(
                            actor_account_id=context.actor_account_id,
                            workspace_id=uuid4(),
                            membership_id=context.membership_id,
                            role=WorkspaceRole.ADMIN,
                            correlation_id=uuid4(),
                        ),
                        membership_id,
                        now=now,
                    )

            delivery = DevelopmentActivationOutbox()
            async with transactional_session(sessions) as session:
                expired_member = await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                ).provision(_command(context, "expired-member@example.invalid"), now=now)
            expired = delivery.drain()[0]
            async with transactional_session(sessions) as session:
                outcome = await MemberActivationService(
                    SqlAlchemyMemberActivationRepository(session, credentials),
                    credentials,
                    Argon2idPasswordService(),
                    delivery,
                ).activate(
                    ActivationAttempt(
                        expired.value,
                        SecretText("synthetic-first-password"),
                        uuid4(),
                        now + timedelta(hours=24),
                    )
                )
                assert not outcome.activated

            async with sessions() as session:
                account_count = await session.scalar(
                    select(func.count())
                    .select_from(UserAccount)
                    .where(UserAccount.normalized_email == "same-member@example.invalid")
                )
                membership_count = await session.scalar(
                    select(func.count())
                    .select_from(WorkspaceMembership)
                    .where(
                        WorkspaceMembership.workspace_id == context.workspace_id,
                        WorkspaceMembership.user_account_id
                        == select(UserAccount.id)
                        .where(UserAccount.normalized_email == "same-member@example.invalid")
                        .scalar_subquery(),
                    )
                )
                challenge = await session.scalar(
                    select(ActivationChallenge).where(
                        ActivationChallenge.membership_id == expired_member.membership_id
                    )
                )
                assert account_count == 1
                assert membership_count == 1
                assert challenge is not None and challenge.status == "EXPIRED"
        finally:
            await engine.dispose()
            await _clear(migrated_database)

    asyncio.run(exercise())
