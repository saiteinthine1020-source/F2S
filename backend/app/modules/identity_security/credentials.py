"""Purpose-separated opaque credential, keyed-digest, and lifecycle primitives."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from app.modules.identity_security.values import KeyedDigest, SecretBytes, SecretText

MINIMUM_OPAQUE_ENTROPY_BYTES: Final = 32
MINIMUM_DIGEST_KEY_BYTES: Final = 32
DEFAULT_CHALLENGE_LIFETIME: Final = timedelta(hours=24)
_DIGEST_DOMAIN: Final = b"f2s-identity-digest-v1\x00"


class DigestPurpose(StrEnum):
    """Bounded HMAC domains for credentials and concealed abuse subjects."""

    ACCESS_CREDENTIAL = "ACCESS_CREDENTIAL"
    REFRESH_CREDENTIAL = "REFRESH_CREDENTIAL"
    CSRF_CREDENTIAL = "CSRF_CREDENTIAL"
    ACTIVATION_CHALLENGE = "ACTIVATION_CHALLENGE"
    RECOVERY_CHALLENGE = "RECOVERY_CHALLENGE"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"
    LOGIN_IDENTIFIER = "LOGIN_IDENTIFIER"
    RECOVERY_RECIPIENT = "RECOVERY_RECIPIENT"
    FINANCIAL_EVENT_CURSOR = "FINANCIAL_EVENT_CURSOR"


class OpaqueCredentialPurpose(StrEnum):
    """Purposes for which a new bearer or challenge value may be generated."""

    ACCESS_CREDENTIAL = DigestPurpose.ACCESS_CREDENTIAL
    REFRESH_CREDENTIAL = DigestPurpose.REFRESH_CREDENTIAL
    CSRF_CREDENTIAL = DigestPurpose.CSRF_CREDENTIAL
    ACTIVATION_CHALLENGE = DigestPurpose.ACTIVATION_CHALLENGE
    RECOVERY_CHALLENGE = DigestPurpose.RECOVERY_CHALLENGE
    OWNERSHIP_TRANSFER = DigestPurpose.OWNERSHIP_TRANSFER


class CredentialVerification(StrEnum):
    """Internal lifecycle result that contains no bearer value or identifier."""

    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"


class CredentialLifecycleError(Exception):
    """Safe lifecycle failure containing only a bounded result code."""

    def __init__(self, result: CredentialVerification) -> None:
        self.result = result
        super().__init__(result.value)


def require_aware(value: datetime) -> None:
    """Reject naive or offset-less timestamps at security boundaries."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")


@dataclass(frozen=True, slots=True)
class StoredOpaqueCredential:
    """Digest-only persistence material and immutable lifecycle evidence."""

    purpose: OpaqueCredentialPurpose
    digest: KeyedDigest
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        require_aware(self.issued_at)
        require_aware(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("EXPIRY_MUST_FOLLOW_ISSUE")
        for lifecycle_time in (self.consumed_at, self.revoked_at):
            if lifecycle_time is not None:
                require_aware(lifecycle_time)


@dataclass(frozen=True, slots=True)
class IssuedOpaqueCredential:
    """One clear value for delivery plus its digest-only persistence record."""

    value: SecretText
    record: StoredOpaqueCredential


class KeyedDigestService:
    """HMAC-SHA-256 with explicit purpose domain separation."""

    def __init__(self, key: SecretBytes) -> None:
        if len(key.reveal()) < MINIMUM_DIGEST_KEY_BYTES:
            raise ValueError("DIGEST_KEY_TOO_SHORT")
        self._key = key

    def digest(self, purpose: DigestPurpose, value: SecretText) -> KeyedDigest:
        """Create a fixed-size purpose-bound digest for persistence."""
        message = _DIGEST_DOMAIN + purpose.value.encode("ascii") + b"\x00" + value.reveal().encode()
        encoded = hmac.new(self._key.reveal(), message, hashlib.sha256).hexdigest()
        return KeyedDigest(encoded)

    def verify(self, purpose: DigestPurpose, presented: SecretText, expected: KeyedDigest) -> bool:
        """Compare a newly derived digest using the standard constant-time primitive."""
        candidate = self.digest(purpose, presented)
        return hmac.compare_digest(candidate.for_persistence(), expected.for_persistence())


class OpaqueCredentialService:
    """Generate high-entropy values and validate their immutable lifecycle records."""

    def __init__(
        self,
        digests: KeyedDigestService,
        *,
        entropy_bytes: int = MINIMUM_OPAQUE_ENTROPY_BYTES,
    ) -> None:
        if entropy_bytes < MINIMUM_OPAQUE_ENTROPY_BYTES:
            raise ValueError("OPAQUE_ENTROPY_TOO_LOW")
        self._digests = digests
        self._entropy_bytes = entropy_bytes

    def issue(
        self,
        purpose: OpaqueCredentialPurpose,
        *,
        now: datetime,
        lifetime: timedelta,
    ) -> IssuedOpaqueCredential:
        """Return one client-deliverable value and one digest-only server record."""
        require_aware(now)
        if lifetime <= timedelta(0):
            raise ValueError("LIFETIME_MUST_BE_POSITIVE")
        value = SecretText(secrets.token_urlsafe(self._entropy_bytes))
        digest = self._digests.digest(DigestPurpose(purpose.value), value)
        record = StoredOpaqueCredential(
            purpose=purpose,
            digest=digest,
            issued_at=now,
            expires_at=now + lifetime,
        )
        return IssuedOpaqueCredential(value=value, record=record)

    def fingerprint(self, purpose: OpaqueCredentialPurpose, presented: SecretText) -> KeyedDigest:
        """Derive a purpose-bound lookup digest without exposing the bearer value."""
        return self._digests.digest(DigestPurpose(purpose.value), presented)

    def verify(
        self,
        purpose: OpaqueCredentialPurpose,
        presented: SecretText,
        record: StoredOpaqueCredential,
        *,
        now: datetime,
    ) -> CredentialVerification:
        """Validate purpose, digest, expiry, revocation, and one-time use safely."""
        require_aware(now)
        digest_matches = self._digests.verify(
            DigestPurpose(purpose.value), presented, record.digest
        )
        if record.revoked_at is not None:
            return CredentialVerification.REVOKED
        if record.consumed_at is not None:
            return CredentialVerification.CONSUMED
        if now >= record.expires_at:
            return CredentialVerification.EXPIRED
        if purpose is not record.purpose or not digest_matches:
            return CredentialVerification.INVALID
        return CredentialVerification.VALID

    def consume(
        self,
        purpose: OpaqueCredentialPurpose,
        presented: SecretText,
        record: StoredOpaqueCredential,
        *,
        now: datetime,
    ) -> StoredOpaqueCredential:
        """Verify and return single-use evidence or one bounded failure code."""
        result = self.verify(purpose, presented, record, now=now)
        if result is not CredentialVerification.VALID:
            raise CredentialLifecycleError(result)
        return replace(record, consumed_at=now)

    def revoke(self, record: StoredOpaqueCredential, *, now: datetime) -> StoredOpaqueCredential:
        """Return immutable revocation evidence without recovering its bearer value."""
        require_aware(now)
        if record.revoked_at is not None:
            return record
        return replace(record, revoked_at=now)
