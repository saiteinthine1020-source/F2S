"""Configured Argon2id password hashing with safe verification outcomes."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.modules.identity_security.values import PasswordDigest, SecretText

MINIMUM_PASSWORD_CHARACTERS: Final = 15
MAXIMUM_PASSWORD_CHARACTERS: Final = 1024


@dataclass(frozen=True, slots=True)
class Argon2idParameters:
    """Versioned initial benchmark candidate from the security design."""

    memory_cost_kib: int = 65_536
    time_cost: int = 3
    parallelism: int = 1
    hash_length: int = 32
    salt_length: int = 16

    def __post_init__(self) -> None:
        if (
            min(
                self.memory_cost_kib,
                self.time_cost,
                self.parallelism,
                self.hash_length,
                self.salt_length,
            )
            <= 0
        ):
            raise ValueError("ARGON2_PARAMETER_INVALID")


class PasswordPolicyCode(StrEnum):
    """Bounded validation outcomes that never echo password content."""

    TOO_SHORT = "PASSWORD_TOO_SHORT"
    TOO_LONG = "PASSWORD_TOO_LONG"
    BLOCKED = "PASSWORD_BLOCKED"


class PasswordPolicyError(Exception):
    """Password-policy failure containing only a stable safe code."""

    def __init__(self, code: PasswordPolicyCode) -> None:
        self.code = code
        super().__init__(code.value)


class PasswordBlocklist(Protocol):
    """Injectable compromised/context-specific password screening port."""

    def contains(self, password: SecretText) -> bool:
        """Return a concealed result without retaining or logging the candidate."""
        ...


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    """Safe verifier result and successful-login rehash signal."""

    matches: bool
    needs_rehash: bool


class Argon2idPasswordService:
    """Hash new passwords and verify stored Argon2id encodings."""

    def __init__(
        self,
        parameters: Argon2idParameters | None = None,
        *,
        blocklist: PasswordBlocklist | None = None,
    ) -> None:
        self.parameters = parameters or Argon2idParameters()
        self._blocklist = blocklist
        self._hasher = PasswordHasher(
            time_cost=self.parameters.time_cost,
            memory_cost=self.parameters.memory_cost_kib,
            parallelism=self.parameters.parallelism,
            hash_len=self.parameters.hash_length,
            salt_len=self.parameters.salt_length,
            type=Type.ID,
        )

    def hash(self, password: SecretText) -> PasswordDigest:
        """Validate a new password and return only its encoded Argon2id verifier."""
        self._validate_new_password(password)
        return PasswordDigest(self._hasher.hash(password.reveal()))

    def verify(self, password: SecretText, expected: PasswordDigest) -> PasswordVerification:
        """Return one safe result for mismatch or malformed verifier input."""
        encoded = expected.for_persistence()
        try:
            self._hasher.verify(encoded, password.reveal())
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return PasswordVerification(matches=False, needs_rehash=False)
        return PasswordVerification(
            matches=True,
            needs_rehash=self._hasher.check_needs_rehash(encoded),
        )

    def needs_rehash(self, expected: PasswordDigest) -> bool:
        """Return true when parameters differ or the stored encoding is unusable."""
        try:
            return self._hasher.check_needs_rehash(expected.for_persistence())
        except (InvalidHashError, VerificationError):
            return True

    def _validate_new_password(self, password: SecretText) -> None:
        length = len(password.reveal())
        if length < MINIMUM_PASSWORD_CHARACTERS:
            raise PasswordPolicyError(PasswordPolicyCode.TOO_SHORT)
        if length > MAXIMUM_PASSWORD_CHARACTERS:
            raise PasswordPolicyError(PasswordPolicyCode.TOO_LONG)
        if self._blocklist is not None and self._blocklist.contains(password):
            raise PasswordPolicyError(PasswordPolicyCode.BLOCKED)
