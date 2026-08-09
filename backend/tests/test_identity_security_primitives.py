"""Focused password, opaque credential, lifecycle, abuse, and redaction tests."""

import asyncio
import base64
import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.identity_security import (
    DEFAULT_CHALLENGE_LIFETIME,
    AbuseScope,
    AbuseSubject,
    Argon2idParameters,
    Argon2idPasswordService,
    CredentialLifecycleError,
    CredentialVerification,
    DigestPurpose,
    FixedWindowRateLimitPolicy,
    KeyedDigest,
    KeyedDigestService,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordBlocklist,
    PasswordDigest,
    PasswordPolicyCode,
    PasswordPolicyError,
    ProgressiveLoginLockoutPolicy,
    RateLimitDecision,
    RateLimiter,
    RateLimitRequest,
    SecretBytes,
    SecretText,
)

_SYNTHETIC_DIGEST_KEY = SecretBytes(b"synthetic-test-only-key-material-not-for-use")


class SyntheticBlocklist(PasswordBlocklist):
    """Test-only screen that compares one clearly artificial candidate."""

    def contains(self, password: SecretText) -> bool:
        return hmac.compare_digest(password.reveal(), "synthetic-blocked-password-candidate")


def create_credential_service() -> OpaqueCredentialService:
    """Create the credential service without exposing key bytes in test output."""
    return OpaqueCredentialService(KeyedDigestService(_SYNTHETIC_DIGEST_KEY))


def test_argon2id_hash_verify_unique_salt_and_configured_parameters() -> None:
    """New password verifiers use the reviewed Argon2id candidate and random salts."""
    service = Argon2idPasswordService()
    password = SecretText("synthetic password candidate for hashing")

    first = service.hash(password)
    second = service.hash(password)
    encoded = first.for_persistence()

    assert encoded.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
    assert not hmac.compare_digest(encoded, second.for_persistence())
    assert service.verify(password, first).matches is True
    assert service.verify(SecretText("synthetic incorrect candidate"), first).matches is False
    assert service.needs_rehash(first) is False


def test_argon2id_rehash_detection_and_malformed_verifier_are_safe() -> None:
    """Successful verification reports old parameters; malformed input never escapes."""
    older = Argon2idPasswordService(
        Argon2idParameters(memory_cost_kib=8_192, time_cost=2, parallelism=1)
    )
    current = Argon2idPasswordService()
    password = SecretText("synthetic password candidate for rehash")
    old_digest = older.hash(password)

    result = current.verify(password, old_digest)
    assert result.matches is True
    assert result.needs_rehash is True
    assert current.needs_rehash(old_digest) is True

    malformed = PasswordDigest("synthetic-malformed-argon2-encoding")
    assert current.verify(password, malformed).matches is False
    assert current.needs_rehash(malformed) is True


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("short-canary", PasswordPolicyCode.TOO_SHORT),
        ("x" * 1_025, PasswordPolicyCode.TOO_LONG),
        (
            "synthetic-blocked-password-candidate",
            PasswordPolicyCode.BLOCKED,
        ),
    ],
)
def test_password_policy_errors_never_echo_candidate(
    candidate: str, expected: PasswordPolicyCode
) -> None:
    """Length and blocklist failures expose only one bounded validation code."""
    service = Argon2idPasswordService(blocklist=SyntheticBlocklist())
    with pytest.raises(PasswordPolicyError) as failure:
        service.hash(SecretText(candidate))
    assert failure.value.code is expected
    assert str(failure.value) == expected.value
    assert candidate not in str(failure.value)


def test_opaque_values_have_minimum_entropy_and_digest_only_records() -> None:
    """Generated bearer values are unique 256-bit inputs absent from stored records."""
    service = create_credential_service()
    now = datetime.now(UTC)
    fingerprints: set[bytes] = set()

    for _ in range(128):
        issued = service.issue(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            now=now,
            lifetime=DEFAULT_CHALLENGE_LIFETIME,
        )
        raw = issued.value.reveal()
        padding = "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(raw + padding)
        assert len(decoded) >= 32
        fingerprints.add(hashlib.sha256(decoded).digest())
        assert not hasattr(issued.record, "value")
        assert len(issued.record.digest.for_persistence()) == 64

    assert len(fingerprints) == 128


def test_keyed_digests_are_purpose_separated_and_constant_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrong-purpose verification fails and uses compare_digest for equal-size outputs."""
    real_compare = hmac.compare_digest
    comparisons = 0

    def observe(left: str, right: str) -> bool:
        nonlocal comparisons
        comparisons += 1
        return real_compare(left, right)

    monkeypatch.setattr(hmac, "compare_digest", observe)
    service = create_credential_service()
    now = datetime.now(UTC)
    issued = service.issue(
        OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
        now=now,
        lifetime=DEFAULT_CHALLENGE_LIFETIME,
    )

    assert (
        service.verify(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            issued.value,
            issued.record,
            now=now,
        )
        is CredentialVerification.VALID
    )
    assert (
        service.verify(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            issued.record,
            now=now,
        )
        is CredentialVerification.INVALID
    )
    with pytest.raises(CredentialLifecycleError) as wrong_purpose:
        service.consume(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            issued.record,
            now=now,
        )
    assert wrong_purpose.value.result is CredentialVerification.INVALID
    assert comparisons == 3


def test_expired_consumed_and_revoked_credentials_fail_without_replay() -> None:
    """Expiry, one-time consumption, replay, and revocation are explicit and immutable."""
    service = create_credential_service()
    now = datetime.now(UTC)
    issued = service.issue(
        OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
        now=now,
        lifetime=DEFAULT_CHALLENGE_LIFETIME,
    )

    consumed = service.consume(
        OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
        issued.value,
        issued.record,
        now=now + timedelta(minutes=1),
    )
    assert (
        service.verify(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            consumed,
            now=now + timedelta(minutes=1),
        )
        is CredentialVerification.CONSUMED
    )
    with pytest.raises(CredentialLifecycleError) as replay:
        service.consume(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            consumed,
            now=now + timedelta(minutes=2),
        )
    assert replay.value.result is CredentialVerification.CONSUMED

    revoked = service.revoke(issued.record, now=now + timedelta(minutes=1))
    assert (
        service.verify(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            revoked,
            now=now + timedelta(minutes=1),
        )
        is CredentialVerification.REVOKED
    )
    assert (
        service.verify(
            OpaqueCredentialPurpose.RECOVERY_CHALLENGE,
            issued.value,
            issued.record,
            now=issued.record.expires_at,
        )
        is CredentialVerification.EXPIRED
    )


def test_security_lifecycle_rejects_naive_time() -> None:
    """Security expiry helpers cannot silently interpret a naive wall-clock time."""
    with pytest.raises(ValueError, match="^TIMEZONE_REQUIRED$"):
        create_credential_service().issue(
            OpaqueCredentialPurpose.OWNERSHIP_TRANSFER,
            now=datetime.now(),
            lifetime=DEFAULT_CHALLENGE_LIFETIME,
        )


def test_rate_limit_and_lockout_policies_are_concealed_and_bounded() -> None:
    """Threshold decisions depend on counters, never an account-existence flag."""
    rate_policy = FixedWindowRateLimitPolicy(limit=5)
    allowed = rate_policy.evaluate(consumed=4, cost=1, reset_after=timedelta(minutes=15))
    denied = rate_policy.evaluate(consumed=5, cost=1, reset_after=timedelta(minutes=15))
    assert allowed == RateLimitDecision(allowed=True)
    assert denied == RateLimitDecision(allowed=False, retry_after=timedelta(minutes=15))

    lockout = ProgressiveLoginLockoutPolicy()
    assert lockout.evaluate(failed_attempts=4).allowed is True
    assert lockout.evaluate(failed_attempts=5).delay == timedelta(seconds=1)
    assert lockout.evaluate(failed_attempts=6).delay == timedelta(seconds=2)
    assert lockout.evaluate(failed_attempts=50).delay == timedelta(minutes=5)


def test_rate_limiter_contract_uses_only_keyed_subjects() -> None:
    """A limiter adapter receives a purpose digest and returns no account detail."""

    class SyntheticLimiter:
        async def consume(self, request: RateLimitRequest) -> RateLimitDecision:
            return FixedWindowRateLimitPolicy(limit=5).evaluate(
                consumed=5,
                cost=request.cost,
                reset_after=timedelta(minutes=15),
            )

    digests = KeyedDigestService(_SYNTHETIC_DIGEST_KEY)
    subject = AbuseSubject(
        digest=digests.digest(
            DigestPurpose.LOGIN_IDENTIFIER,
            SecretText("synthetic-login-identifier@example.invalid"),
        )
    )
    request = RateLimitRequest(scope=AbuseScope.LOGIN_ACCOUNT, subject=subject)
    limiter: RateLimiter = SyntheticLimiter()
    decision = asyncio.run(limiter.consume(request))

    assert decision.allowed is False
    assert decision.retry_after == timedelta(minutes=15)
    assert "synthetic-login-identifier" not in repr(request)
    assert subject.digest.for_persistence() not in repr(request)


def test_sensitive_values_are_redacted_from_repr_format_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ordinary representations never reveal clear values, hashes, keys, or digests."""
    canary = "synthetic-prohibited-value-canary"
    secret = SecretText(canary)
    key = SecretBytes((canary + "-key-material").encode())
    password_digest = PasswordDigest(canary + "-password-digest")
    keyed_digest = KeyedDigest(canary + "-keyed-digest")

    with caplog.at_level(logging.INFO):
        logging.getLogger("f2s.security.test").info(
            "secret=%s key=%r password=%s digest=%r",
            secret,
            key,
            password_digest,
            keyed_digest,
        )

    combined = " ".join(
        (
            str(secret),
            repr(secret),
            f"{secret}",
            repr(key),
            repr(password_digest),
            repr(keyed_digest),
            caplog.text,
        )
    )
    assert canary not in combined
    assert combined.count("<redacted>") >= 7
