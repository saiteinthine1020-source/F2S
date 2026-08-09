"""Framework-free member provisioning and activation orchestration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.identity_security import (
    Argon2idPasswordService,
    IssuedOpaqueCredential,
    KeyedDigestService,
    OpaqueCredentialService,
    PasswordDigest,
    SecretBytes,
    SecretText,
)
from app.modules.member_activation import (
    ActivationAttempt,
    ActivationOutcome,
    DevelopmentActivationOutbox,
    MemberProvisioning,
    MemberRole,
    ProvisionedMember,
    ProvisionMemberCommand,
)
from app.modules.member_activation.service import (
    MemberActivationRepository,
    MemberActivationService,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole


class CapturingMemberRepository(MemberActivationRepository):
    def __init__(self) -> None:
        self.provisioning: MemberProvisioning | None = None
        self.persisted_digest: str | None = None
        self.password_digest: PasswordDigest | None = None
        self.membership_id = uuid4()

    async def provision(
        self, command: MemberProvisioning, credential: IssuedOpaqueCredential
    ) -> ProvisionedMember:
        self.provisioning = command
        self.persisted_digest = credential.record.digest.for_persistence()
        return ProvisionedMember(self.membership_id, command.role)

    async def restart(
        self,
        context: AuthorizationContext,
        membership_id: UUID,
        credential: IssuedOpaqueCredential,
    ) -> str:
        del context, membership_id, credential
        return "member@example.invalid"

    async def activate(
        self, attempt: ActivationAttempt, password_digest: PasswordDigest | None
    ) -> ActivationOutcome:
        del attempt
        self.password_digest = password_digest
        return ActivationOutcome(True)


def _credentials() -> OpaqueCredentialService:
    return OpaqueCredentialService(
        KeyedDigestService(SecretBytes(b"synthetic-member-activation-test-key"))
    )


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor_account_id=uuid4(),
        workspace_id=uuid4(),
        membership_id=uuid4(),
        role=WorkspaceRole.ADMIN,
        correlation_id=uuid4(),
    )


def test_provision_normalizes_fields_and_delivers_clear_value_once() -> None:
    repository = CapturingMemberRepository()
    delivery = DevelopmentActivationOutbox()
    service = MemberActivationService(
        repository, _credentials(), Argon2idPasswordService(), delivery
    )

    result = asyncio.run(
        service.provision(
            ProvisionMemberCommand(
                context=_context(),
                email="  MEMBER@Example.Invalid ",
                display_name="  Member Name  ",
                role=MemberRole.CONTRIBUTOR,
                preferred_language="en",
                timezone="Asia/Tokyo",
            ),
            now=datetime(2026, 8, 9, tzinfo=UTC),
        )
    )

    delivered = delivery.drain()
    assert result.membership_id == repository.membership_id
    assert repository.provisioning is not None
    assert repository.provisioning.normalized_email == "member@example.invalid"
    assert repository.provisioning.display_name == "Member Name"
    assert len(delivered) == 1
    assert delivered[0].recipient == "member@example.invalid"
    assert repository.persisted_digest is not None
    assert delivered[0].value.reveal() not in repository.persisted_digest
    assert "member@example.invalid" not in repr(delivery)
    assert delivery.drain() == ()


def test_activation_hashes_first_password_before_repository_boundary() -> None:
    repository = CapturingMemberRepository()
    service = MemberActivationService(
        repository,
        _credentials(),
        Argon2idPasswordService(),
        DevelopmentActivationOutbox(),
    )

    outcome = asyncio.run(
        service.activate(
            ActivationAttempt(
                value=SecretText("synthetic-activation-value-not-persisted"),
                password=SecretText("synthetic-first-password"),
                correlation_id=uuid4(),
                now=datetime.now(UTC),
            )
        )
    )

    assert outcome.activated
    assert repository.password_digest is not None
    assert "synthetic-first-password" not in repr(repository.password_digest)
    assert repository.password_digest.for_persistence().startswith("$argon2id$")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("preferred_language", "fr", "INVALID_LANGUAGE"),
        ("timezone", "Invalid/Timezone", "INVALID_TIMEZONE"),
        ("display_name", " ", "INVALID_DISPLAY_NAME"),
    ],
)
def test_provision_rejects_invalid_member_fields(field: str, value: str, code: str) -> None:
    repository = CapturingMemberRepository()
    service = MemberActivationService(
        repository,
        _credentials(),
        Argon2idPasswordService(),
        DevelopmentActivationOutbox(),
    )
    values: dict[str, object] = {
        "context": _context(),
        "email": "member@example.invalid",
        "display_name": "Member",
        "role": MemberRole.ADVISOR,
        "preferred_language": "en",
        "timezone": "UTC",
    }
    values[field] = value

    with pytest.raises(ValueError, match=code):
        asyncio.run(service.provision(ProvisionMemberCommand(**values)))  # type: ignore[arg-type]


def test_admin_is_not_an_allowed_provisioning_role() -> None:
    with pytest.raises(ValueError):
        MemberRole("ADMIN")
