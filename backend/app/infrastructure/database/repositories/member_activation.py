"""Workspace-scoped PostgreSQL member provisioning and activation adapter."""

from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.identity_security import ActivationChallenge
from app.infrastructure.database.models.workspace_access import Workspace, WorkspaceMembership
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
    CredentialVerification,
    IssuedOpaqueCredential,
    KeyedDigest,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    StoredOpaqueCredential,
)
from app.modules.member_activation.service import (
    ActivationAttempt,
    ActivationOutcome,
    DuplicateMembership,
    MemberActivationRepository,
    MemberProvisioning,
    ProvisionedMember,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)


class SqlAlchemyMemberActivationRepository(MemberActivationRepository):
    def __init__(self, session: AsyncSession, credentials: OpaqueCredentialService) -> None:
        self._session = session
        self._credentials = credentials

    async def provision(
        self, command: MemberProvisioning, credential: IssuedOpaqueCredential
    ) -> ProvisionedMember:
        await self._require_admin(command.context)
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:identifier, 0))"),
            {"identifier": command.normalized_email},
        )
        account = await self._session.scalar(
            select(UserAccount)
            .where(UserAccount.normalized_email == command.normalized_email)
            .with_for_update()
        )
        if account is None:
            account = UserAccount(
                id=uuid4(),
                normalized_email=command.normalized_email,
                display_name=command.display_name,
                password_digest=None,
                status="PENDING_ACTIVATION",
                preferred_language=command.preferred_language,
                timezone=command.timezone,
            )
            self._session.add(account)
            await self._session.flush()
        elif account.status not in {"PENDING_ACTIVATION", "ACTIVE"}:
            raise DuplicateMembership()

        existing = await self._session.scalar(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.workspace_id == command.context.workspace_id,
                WorkspaceMembership.user_account_id == account.id,
            )
        )
        if existing is not None:
            raise DuplicateMembership()

        membership_id = uuid4()
        membership = WorkspaceMembership(
            id=membership_id,
            workspace_id=command.context.workspace_id,
            user_account_id=account.id,
            role=command.role.value,
            status="PENDING",
        )
        self._session.add(membership)
        await self._session.flush()
        self._add_challenge(command.context.workspace_id, membership_id, account.id, credential)
        await self._session.flush()
        await self._audit(
            context=command.context,
            action=AuditAction.MEMBER_CREATED,
            result=AuditResult.SUCCEEDED,
            membership_id=membership_id,
            audit_context=AuditContext.MEMBERSHIP_ADMINISTRATION,
        )
        return ProvisionedMember(membership_id, command.role)

    async def restart(
        self,
        context: AuthorizationContext,
        membership_id: UUID,
        credential: IssuedOpaqueCredential,
    ) -> str:
        await self._require_admin(context)
        row = (
            await self._session.execute(
                select(WorkspaceMembership, UserAccount.normalized_email)
                .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
                .where(
                    WorkspaceMembership.workspace_id == context.workspace_id,
                    WorkspaceMembership.id == membership_id,
                    WorkspaceMembership.status == "PENDING",
                    WorkspaceMembership.role.in_(("CONTRIBUTOR", "ADVISOR")),
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        membership, email = row
        await self._session.execute(
            update(ActivationChallenge)
            .where(
                ActivationChallenge.workspace_id == context.workspace_id,
                ActivationChallenge.membership_id == membership_id,
                ActivationChallenge.status == "ISSUED",
            )
            .values(
                status="REVOKED",
                revoked_at=credential.record.issued_at,
                revoke_reason_code="RESTARTED",
                version=ActivationChallenge.version + 1,
            )
        )
        self._add_challenge(
            context.workspace_id,
            membership_id,
            membership.user_account_id,
            credential,
        )
        await self._session.flush()
        await self._audit(
            context=context,
            action=AuditAction.ACTIVATION_RESTARTED,
            result=AuditResult.SUCCEEDED,
            membership_id=membership_id,
        )
        return str(email)

    async def activate(
        self, attempt: ActivationAttempt, password_digest: PasswordDigest | None
    ) -> ActivationOutcome:
        lookup = self._credentials.fingerprint(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE, attempt.value
        )
        challenge = await self._session.scalar(
            select(ActivationChallenge)
            .where(ActivationChallenge.challenge_digest == lookup.for_persistence())
            .with_for_update()
        )
        if challenge is None:
            await self._denied_activation(attempt.correlation_id, AuditReason.INVALID_CREDENTIALS)
            return ActivationOutcome(False)

        membership = await self._session.scalar(
            select(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == challenge.workspace_id,
                WorkspaceMembership.id == challenge.membership_id,
                WorkspaceMembership.user_account_id == challenge.user_account_id,
            )
            .with_for_update()
        )
        account = await self._session.scalar(
            select(UserAccount).where(UserAccount.id == challenge.user_account_id).with_for_update()
        )
        record = self._stored(challenge)
        verification = self._credentials.verify(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            attempt.value,
            record,
            now=attempt.now,
        )
        eligible = (
            verification is CredentialVerification.VALID
            and membership is not None
            and account is not None
            and membership.status == "PENDING"
            and membership.role in {"CONTRIBUTOR", "ADVISOR"}
            and account.status in {"PENDING_ACTIVATION", "ACTIVE"}
            and (account.status == "ACTIVE" or password_digest is not None)
        )
        if not eligible:
            if verification is CredentialVerification.EXPIRED:
                challenge.status = "EXPIRED"
            await self._denied_activation(
                attempt.correlation_id,
                self._reason_for(verification),
                workspace_id=challenge.workspace_id,
            )
            return ActivationOutcome(False)

        assert account is not None
        assert membership is not None
        if account.status == "PENDING_ACTIVATION":
            assert password_digest is not None
            account.status = "ACTIVE"
            account.password_digest = password_digest.for_persistence()
            account.version += 1
        membership.status = "ACTIVE"
        membership.version += 1
        challenge.status = "USED"
        challenge.used_at = attempt.now
        challenge.version += 1
        await self._session.flush()
        context = AuthorizationContext(
            actor_account_id=account.id,
            workspace_id=membership.workspace_id,
            membership_id=membership.id,
            role=WorkspaceRole(membership.role),
            correlation_id=attempt.correlation_id,
        )
        await self._audit(
            context=context,
            action=AuditAction.MEMBER_ACTIVATED,
            result=AuditResult.SUCCEEDED,
            membership_id=membership.id,
        )
        return ActivationOutcome(True)

    async def _require_admin(self, context: AuthorizationContext) -> None:
        row = await self._session.scalar(
            select(WorkspaceMembership.id)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.id == context.membership_id,
                WorkspaceMembership.user_account_id == context.actor_account_id,
                WorkspaceMembership.role == context.role.value,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.status == "ACTIVE",
                Workspace.status == "ACTIVE",
            )
        )
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        require_capability(context, Capability.MANAGE_MEMBERS)

    def _add_challenge(
        self,
        workspace_id: UUID,
        membership_id: UUID,
        account_id: UUID,
        credential: IssuedOpaqueCredential,
    ) -> None:
        self._session.add(
            ActivationChallenge(
                id=uuid4(),
                workspace_id=workspace_id,
                membership_id=membership_id,
                user_account_id=account_id,
                challenge_digest=credential.record.digest.for_persistence(),
                digest_algorithm_code="SHA256",
                status="ISSUED",
                issued_at=credential.record.issued_at,
                expires_at=credential.record.expires_at,
            )
        )

    def _stored(self, challenge: ActivationChallenge) -> StoredOpaqueCredential:
        return StoredOpaqueCredential(
            purpose=OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            digest=KeyedDigest(challenge.challenge_digest),
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
            consumed_at=challenge.used_at,
            revoked_at=challenge.revoked_at,
        )

    async def _audit(
        self,
        *,
        context: AuthorizationContext,
        action: AuditAction,
        result: AuditResult,
        membership_id: UUID,
        audit_context: AuditContext = AuditContext.ACTIVATION,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=action,
                module=AuditModule.WORKSPACE_ACCESS,
                result=result,
                correlation_id=context.correlation_id,
                resource_type=AuditResourceType.WORKSPACE_MEMBERSHIP,
                resource_id=membership_id if result is not AuditResult.DENIED else None,
                source=AuditSource.API,
                context=audit_context,
            )
        )

    async def _denied_activation(
        self,
        correlation_id: UUID,
        reason: AuditReason,
        *,
        workspace_id: UUID | None = None,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE if workspace_id is not None else AuditScope.GLOBAL,
                workspace_id=workspace_id,
                actor=AuditActor.system(),
                action=AuditAction.MEMBER_ACTIVATED,
                module=AuditModule.IDENTITY_SECURITY,
                result=AuditResult.DENIED,
                correlation_id=correlation_id,
                resource_type=AuditResourceType.WORKSPACE_MEMBERSHIP,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.ACTIVATION,
            )
        )

    @staticmethod
    def _reason_for(verification: CredentialVerification) -> AuditReason:
        return {
            CredentialVerification.EXPIRED: AuditReason.EXPIRED,
            CredentialVerification.CONSUMED: AuditReason.REPLAY_DETECTED,
            CredentialVerification.REVOKED: AuditReason.REVOKED,
        }.get(verification, AuditReason.INVALID_CREDENTIALS)
