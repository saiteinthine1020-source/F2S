"""PostgreSQL adapter for password change and concealed account recovery."""

from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import AuthSession, RecoveryChallenge
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.account_security import (
    AccountSecurityRepository,
    PasswordChangeAttempt,
    PasswordChangeCandidate,
    RecoveryConfirmation,
)
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
    CredentialVerification,
    IssuedOpaqueCredential,
    KeyedDigest,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    StoredOpaqueCredential,
)


class SqlAlchemyAccountSecurityRepository(AccountSecurityRepository):
    def __init__(self, session: AsyncSession, credentials: OpaqueCredentialService) -> None:
        self._session = session
        self._credentials = credentials

    async def password_change_candidate(
        self, account_id: UUID, current_session_id: UUID
    ) -> PasswordChangeCandidate | None:
        session = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.id == current_session_id,
                AuthSession.user_account_id == account_id,
                AuthSession.status == "ACTIVE",
            )
            .with_for_update()
        )
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == account_id).with_for_update()
        )
        if (
            session is None
            or account is None
            or account.status != "ACTIVE"
            or account.password_digest is None
        ):
            return None
        return PasswordChangeCandidate(account.id, PasswordDigest(account.password_digest))

    async def password_change_denied(self, account_id: UUID, correlation_id: UUID) -> None:
        await self._audit(
            actor=AuditActor.user(account_id),
            action=AuditAction.PASSWORD_CHANGED,
            result=AuditResult.DENIED,
            correlation_id=correlation_id,
            reason=AuditReason.INVALID_CREDENTIALS,
            audit_context=AuditContext.AUTHENTICATION,
        )

    async def change_password(
        self, attempt: PasswordChangeAttempt, password_digest: PasswordDigest
    ) -> bool:
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == attempt.account_id).with_for_update()
        )
        current = await self._session.scalar(
            select(AuthSession)
            .where(
                AuthSession.id == attempt.current_session_id,
                AuthSession.user_account_id == attempt.account_id,
                AuthSession.status == "ACTIVE",
            )
            .with_for_update()
        )
        if account is None or account.status != "ACTIVE" or current is None:
            await self.password_change_denied(attempt.account_id, attempt.correlation_id)
            return False
        account.password_digest = password_digest.for_persistence()
        account.version += 1
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_account_id == account.id,
                AuthSession.status == "ACTIVE",
                AuthSession.id != current.id,
            )
            .values(
                status="REVOKED",
                revoked_at=attempt.now,
                revoke_reason_code="PASSWORD_CHANGED",
                version=AuthSession.version + 1,
            )
        )
        await self._audit(
            actor=AuditActor.user(account.id),
            action=AuditAction.PASSWORD_CHANGED,
            result=AuditResult.SUCCEEDED,
            correlation_id=attempt.correlation_id,
            resource_id=account.id,
            audit_context=AuditContext.AUTHENTICATION,
        )
        await self._audit(
            actor=AuditActor.user(account.id),
            action=AuditAction.SESSION_REVOKED,
            result=AuditResult.SUCCEEDED,
            correlation_id=attempt.correlation_id,
            resource_type=AuditResourceType.SESSION,
            audit_context=AuditContext.AUTHENTICATION,
        )
        return True

    async def issue_recovery(
        self,
        normalized_email: str | None,
        credential: IssuedOpaqueCredential,
        correlation_id: UUID,
    ) -> str | None:
        account: UserAccount | None = None
        if normalized_email is not None:
            await self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identifier, 0))"),
                {"identifier": normalized_email},
            )
            account = await self._session.scalar(
                select(UserAccount)
                .where(UserAccount.normalized_email == normalized_email)
                .with_for_update()
            )
        eligible = (
            account is not None
            and account.status == "ACTIVE"
            and account.password_digest is not None
            and not await self._is_workspace_owner(account.id)
        )
        if eligible:
            assert account is not None
            await self._session.execute(
                update(RecoveryChallenge)
                .where(
                    RecoveryChallenge.user_account_id == account.id,
                    RecoveryChallenge.status == "ISSUED",
                )
                .values(
                    status="REVOKED",
                    revoked_at=credential.record.issued_at,
                    revoke_reason_code="RESTARTED",
                    version=RecoveryChallenge.version + 1,
                )
            )
            self._session.add(
                RecoveryChallenge(
                    id=uuid4(),
                    user_account_id=account.id,
                    challenge_digest=credential.record.digest.for_persistence(),
                    digest_algorithm_code="SHA256",
                    status="ISSUED",
                    issued_at=credential.record.issued_at,
                    expires_at=credential.record.expires_at,
                )
            )
        await self._audit(
            actor=AuditActor.system(),
            action=AuditAction.RECOVERY_REQUESTED,
            result=AuditResult.SUCCEEDED,
            correlation_id=correlation_id,
        )
        return account.normalized_email if eligible and account is not None else None

    async def confirm_recovery(
        self, confirmation: RecoveryConfirmation, password_digest: PasswordDigest
    ) -> bool:
        lookup = self._credentials.fingerprint(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE, confirmation.value
        )
        challenge = await self._session.scalar(
            select(RecoveryChallenge)
            .where(RecoveryChallenge.challenge_digest == lookup.for_persistence())
            .with_for_update()
        )
        if challenge is None:
            await self._recovery_denied(
                confirmation.correlation_id, AuditReason.INVALID_CREDENTIALS
            )
            return False
        challenge.attempt_count += 1
        record = StoredOpaqueCredential(
            purpose=OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            digest=KeyedDigest(challenge.challenge_digest),
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
            consumed_at=challenge.used_at,
            revoked_at=challenge.revoked_at,
        )
        verification = self._credentials.verify(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            confirmation.value,
            record,
            now=confirmation.now,
        )
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == challenge.user_account_id).with_for_update()
        )
        eligible = (
            verification is CredentialVerification.VALID
            and account is not None
            and account.status == "ACTIVE"
            and not await self._is_workspace_owner(challenge.user_account_id)
        )
        if not eligible:
            if verification is CredentialVerification.EXPIRED:
                challenge.status = "EXPIRED"
            challenge.version += 1
            await self._recovery_denied(confirmation.correlation_id, self._reason_for(verification))
            return False
        assert account is not None
        account.password_digest = password_digest.for_persistence()
        account.version += 1
        challenge.status = "USED"
        challenge.used_at = confirmation.now
        challenge.version += 1
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_account_id == account.id,
                AuthSession.status == "ACTIVE",
            )
            .values(
                status="REVOKED",
                revoked_at=confirmation.now,
                revoke_reason_code="ACCOUNT_RECOVERY",
                version=AuthSession.version + 1,
            )
        )
        await self._audit(
            actor=AuditActor.user(account.id),
            action=AuditAction.RECOVERY_COMPLETED,
            result=AuditResult.SUCCEEDED,
            correlation_id=confirmation.correlation_id,
            resource_id=account.id,
        )
        await self._audit(
            actor=AuditActor.user(account.id),
            action=AuditAction.SESSION_REVOKED,
            result=AuditResult.SUCCEEDED,
            correlation_id=confirmation.correlation_id,
            resource_type=AuditResourceType.SESSION,
        )
        return True

    async def _is_workspace_owner(self, account_id: UUID) -> bool:
        owner = await self._session.scalar(
            select(Workspace.id)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.id == Workspace.owner_membership_id,
            )
            .where(WorkspaceMembership.user_account_id == account_id)
            .limit(1)
        )
        return owner is not None

    async def _recovery_denied(self, correlation_id: UUID, reason: AuditReason) -> None:
        await self._audit(
            actor=AuditActor.system(),
            action=AuditAction.RECOVERY_COMPLETED,
            result=AuditResult.DENIED,
            correlation_id=correlation_id,
            reason=reason,
        )

    async def _audit(
        self,
        *,
        actor: AuditActor,
        action: AuditAction,
        result: AuditResult,
        correlation_id: UUID,
        resource_type: AuditResourceType = AuditResourceType.USER_ACCOUNT,
        resource_id: UUID | None = None,
        reason: AuditReason | None = None,
        audit_context: AuditContext = AuditContext.RECOVERY,
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
                context=audit_context,
            )
        )

    @staticmethod
    def _reason_for(verification: CredentialVerification) -> AuditReason:
        return {
            CredentialVerification.EXPIRED: AuditReason.EXPIRED,
            CredentialVerification.CONSUMED: AuditReason.REPLAY_DETECTED,
            CredentialVerification.REVOKED: AuditReason.REVOKED,
        }.get(verification, AuditReason.INVALID_CREDENTIALS)
