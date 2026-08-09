"""PostgreSQL adapter for opaque login, rotation, authentication, and logout."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import AuthSession
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.identity_security import (
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretText,
)
from app.modules.sessions import (
    AuthenticatedSession,
    LoginCandidate,
    LogoutAttempt,
    LogoutScope,
    RotationAttempt,
    RotationLease,
    SessionCredentialBundle,
    SessionRepository,
)


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, session: AsyncSession, credentials: OpaqueCredentialService) -> None:
        self._session = session
        self._credentials = credentials

    async def login_candidate(self, normalized_email: str | None) -> LoginCandidate | None:
        if normalized_email is None:
            return None
        account = await self._session.scalar(
            select(UserAccount)
            .where(UserAccount.normalized_email == normalized_email)
            .with_for_update()
        )
        if account is None or account.password_digest is None:
            return None
        return LoginCandidate(
            account_id=account.id,
            password_digest=PasswordDigest(account.password_digest),
            active=account.status == "ACTIVE",
        )

    async def login_failed(self, correlation_id: UUID) -> None:
        await self._audit(
            actor=AuditActor.system(),
            action=AuditAction.LOGIN_FAILED,
            result=AuditResult.FAILED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.USER_ACCOUNT,
            reason=AuditReason.INVALID_CREDENTIALS,
        )

    async def create_session(
        self,
        account_id: UUID,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
        replacement_password_digest: PasswordDigest | None,
    ) -> None:
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == account_id).with_for_update()
        )
        if account is None or account.status != "ACTIVE":
            await self.login_failed(correlation_id)
            return
        if replacement_password_digest is not None:
            account.password_digest = replacement_password_digest.for_persistence()
            account.version += 1
        session_id = uuid4()
        self._session.add(
            AuthSession(
                id=session_id,
                user_account_id=account_id,
                family_id=uuid4(),
                rotated_from_session_id=None,
                access_credential_digest=bundle.access.record.digest.for_persistence(),
                refresh_credential_digest=bundle.refresh.record.digest.for_persistence(),
                csrf_credential_digest=bundle.csrf.record.digest.for_persistence(),
                digest_algorithm_code="SHA256",
                status="ACTIVE",
                issued_at=bundle.access.record.issued_at,
                access_expires_at=bundle.access.record.expires_at,
                refresh_idle_expires_at=bundle.refresh.record.expires_at,
                absolute_expires_at=bundle.absolute_expires_at,
            )
        )
        await self._session.flush()
        actor = AuditActor.user(account_id)
        await self._audit(
            actor=actor,
            action=AuditAction.LOGIN_SUCCEEDED,
            result=AuditResult.SUCCEEDED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.USER_ACCOUNT,
            resource_id=account_id,
        )
        await self._audit(
            actor=actor,
            action=AuditAction.SESSION_CREATED,
            result=AuditResult.SUCCEEDED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.SESSION,
            resource_id=session_id,
        )

    async def prepare_rotation(self, attempt: RotationAttempt) -> RotationLease | None:
        session = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.refresh_credential_digest
                == self._fingerprint(OpaqueCredentialPurpose.REFRESH_CREDENTIAL, attempt.refresh)
            )
            .with_for_update()
        )
        if session is None:
            await self._rotation_denied(attempt.correlation_id, AuditReason.INVALID_CREDENTIALS)
            return None
        csrf_matches = session.csrf_credential_digest == self._fingerprint(
            OpaqueCredentialPurpose.CSRF_CREDENTIAL, attempt.csrf
        )
        if not csrf_matches:
            await self._rotation_denied(attempt.correlation_id, AuditReason.INVALID_CREDENTIALS)
            return None
        if session.status == "ROTATED":
            await self._record_reuse(session, attempt.now, attempt.correlation_id)
            return None
        if session.status != "ACTIVE":
            await self._rotation_denied(attempt.correlation_id, AuditReason.REVOKED)
            return None

        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == session.user_account_id).with_for_update()
        )
        if account is None or account.status != "ACTIVE":
            await self._revoke_active_family(session.family_id, attempt.now, "ACCOUNT_INACTIVE")
            await self._rotation_denied(attempt.correlation_id, AuditReason.ACCOUNT_INACTIVE)
            return None
        if (
            attempt.now >= session.refresh_idle_expires_at
            or attempt.now >= session.absolute_expires_at
        ):
            session.status = "EXPIRED"
            session.version += 1
            await self._rotation_denied(attempt.correlation_id, AuditReason.EXPIRED)
            return None
        return RotationLease(
            parent_session_id=session.id,
            account_id=session.user_account_id,
            family_id=session.family_id,
            absolute_expires_at=session.absolute_expires_at,
        )

    async def complete_rotation(
        self,
        lease: RotationLease,
        bundle: SessionCredentialBundle,
        correlation_id: UUID,
    ) -> None:
        parent = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.id == lease.parent_session_id,
                AuthSession.status == "ACTIVE",
                AuthSession.family_id == lease.family_id,
                AuthSession.user_account_id == lease.account_id,
            )
            .with_for_update()
        )
        if parent is None:
            raise RuntimeError("ROTATION_LEASE_INVALID")
        parent.status = "ROTATED"
        parent.last_used_at = bundle.access.record.issued_at
        parent.last_rotated_at = bundle.access.record.issued_at
        parent.version += 1
        await self._session.flush()

        child_id = uuid4()
        self._session.add(
            AuthSession(
                id=child_id,
                user_account_id=lease.account_id,
                family_id=lease.family_id,
                rotated_from_session_id=parent.id,
                access_credential_digest=bundle.access.record.digest.for_persistence(),
                refresh_credential_digest=bundle.refresh.record.digest.for_persistence(),
                csrf_credential_digest=bundle.csrf.record.digest.for_persistence(),
                digest_algorithm_code="SHA256",
                status="ACTIVE",
                issued_at=bundle.access.record.issued_at,
                access_expires_at=bundle.access.record.expires_at,
                refresh_idle_expires_at=bundle.refresh.record.expires_at,
                absolute_expires_at=lease.absolute_expires_at,
            )
        )
        await self._session.flush()
        await self._audit(
            actor=AuditActor.user(lease.account_id),
            action=AuditAction.SESSION_ROTATED,
            result=AuditResult.SUCCEEDED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.SESSION,
            resource_id=child_id,
        )

    async def authenticate_access(
        self, access: SecretText, *, now: datetime, correlation_id: UUID
    ) -> AuthenticatedSession | None:
        session = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.access_credential_digest
                == self._fingerprint(OpaqueCredentialPurpose.ACCESS_CREDENTIAL, access)
            )
            .with_for_update()
        )
        if session is None or session.status != "ACTIVE":
            return None
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == session.user_account_id).with_for_update()
        )
        if account is None or account.status != "ACTIVE":
            await self._revoke_active_family(session.family_id, now, "ACCOUNT_INACTIVE")
            await self._audit(
                actor=AuditActor.user(session.user_account_id),
                action=AuditAction.SESSION_REVOKED,
                result=AuditResult.SUCCEEDED,
                correlation_id=correlation_id,
                resource_type=AuditResourceType.SESSION,
                resource_id=session.id,
                reason=AuditReason.ACCOUNT_INACTIVE,
            )
            return None
        if (
            now >= session.access_expires_at
            or now >= session.refresh_idle_expires_at
            or now >= session.absolute_expires_at
        ):
            session.status = "EXPIRED"
            session.version += 1
            return None
        session.last_used_at = now
        return AuthenticatedSession(account.id, session.id)

    async def logout(self, attempt: LogoutAttempt) -> None:
        session = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.refresh_credential_digest
                == self._fingerprint(OpaqueCredentialPurpose.REFRESH_CREDENTIAL, attempt.refresh)
            )
            .with_for_update()
        )
        if session is None:
            return
        if session.csrf_credential_digest != self._fingerprint(
            OpaqueCredentialPurpose.CSRF_CREDENTIAL, attempt.csrf
        ):
            return
        if session.status == "ROTATED":
            await self._record_reuse(session, attempt.now, attempt.correlation_id)
            return
        if session.status != "ACTIVE":
            return
        if attempt.scope is LogoutScope.ALL:
            await self._revoke_active_account(session.user_account_id, attempt.now, "LOGOUT_ALL")
        else:
            await self._revoke_active_family(session.family_id, attempt.now, "LOGOUT")
        await self._audit(
            actor=AuditActor.user(session.user_account_id),
            action=AuditAction.SESSION_REVOKED,
            result=AuditResult.SUCCEEDED,
            correlation_id=attempt.correlation_id,
            resource_type=AuditResourceType.SESSION,
            resource_id=session.id,
        )

    def _fingerprint(self, purpose: OpaqueCredentialPurpose, value: SecretText) -> str:
        return self._credentials.fingerprint(purpose, value).for_persistence()

    async def _record_reuse(
        self, session: AuthSession, now: datetime, correlation_id: UUID
    ) -> None:
        await self._revoke_active_family(session.family_id, now, "REFRESH_REUSE")
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.family_id == session.family_id,
                AuthSession.status == "ROTATED",
            )
            .values(
                status="REUSE_DETECTED",
                revoked_at=now,
                revoke_reason_code="REFRESH_REUSE",
                reuse_detected_at=now,
                version=AuthSession.version + 1,
            )
        )
        await self._audit(
            actor=AuditActor.user(session.user_account_id),
            action=AuditAction.SESSION_REUSE_DETECTED,
            result=AuditResult.DENIED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.SESSION,
            reason=AuditReason.REPLAY_DETECTED,
        )

    async def _revoke_active_family(self, family_id: UUID, now: datetime, reason: str) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.family_id == family_id, AuthSession.status == "ACTIVE")
            .values(
                status="REVOKED",
                revoked_at=now,
                revoke_reason_code=reason,
                version=AuthSession.version + 1,
            )
        )

    async def _revoke_active_account(self, account_id: UUID, now: datetime, reason: str) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_account_id == account_id,
                AuthSession.status == "ACTIVE",
            )
            .values(
                status="REVOKED",
                revoked_at=now,
                revoke_reason_code=reason,
                version=AuthSession.version + 1,
            )
        )

    async def _rotation_denied(self, correlation_id: UUID, reason: AuditReason) -> None:
        await self._audit(
            actor=AuditActor.system(),
            action=AuditAction.SESSION_ROTATED,
            result=AuditResult.DENIED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.SESSION,
            reason=reason,
        )

    async def _audit(
        self,
        *,
        actor: AuditActor,
        action: AuditAction,
        result: AuditResult,
        correlation_id: UUID,
        resource_type: AuditResourceType,
        resource_id: UUID | None = None,
        reason: AuditReason | None = None,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.GLOBAL,
                actor=actor,
                action=action,
                module=AuditModule.IDENTITY_SECURITY,
                result=result,
                correlation_id=correlation_id,
                resource_type=resource_type,
                resource_id=resource_id,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.AUTHENTICATION,
            )
        )
