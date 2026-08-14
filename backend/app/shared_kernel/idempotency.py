"""Stable opaque idempotency identifiers and request fingerprints."""

import hashlib
import re
from dataclasses import dataclass

_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_OPERATION = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or _KEY.fullmatch(self.value) is None:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

    def digest(self) -> str:
        return hashlib.sha256(self.value.encode("ascii")).hexdigest()

    def __repr__(self) -> str:
        return "IdempotencyKey(**redacted**)"


@dataclass(frozen=True, slots=True)
class OperationCode:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or _OPERATION.fullmatch(self.value) is None:
            raise ValueError("INVALID_OPERATION_CODE")


@dataclass(frozen=True, slots=True)
class RequestFingerprint:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or _DIGEST.fullmatch(self.value) is None:
            raise ValueError("INVALID_REQUEST_FINGERPRINT")

    @classmethod
    def from_canonical_bytes(cls, value: bytes) -> "RequestFingerprint":
        if type(value) is not bytes:
            raise ValueError("INVALID_CANONICAL_REQUEST")
        return cls(hashlib.sha256(value).hexdigest())

    def __repr__(self) -> str:
        return "RequestFingerprint(**redacted**)"
