"""Explicit redacted values for security-sensitive inputs and persistence material."""

from typing import Final

REDACTED: Final = "<redacted>"


class SecretText:
    """A string whose ordinary representations never reveal its value."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the value only at an explicit cryptographic or delivery boundary."""
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(REDACTED, format_spec)


class SecretBytes:
    """Byte key material with redacted string, repr, and formatted output."""

    __slots__ = ("_value",)

    def __init__(self, value: bytes) -> None:
        self._value = bytes(value)

    def reveal(self) -> bytes:
        """Return a copy only to a cryptographic boundary."""
        return bytes(self._value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(REDACTED, format_spec)


class PasswordDigest:
    """An encoded verifier whose ordinary representations remain redacted."""

    __slots__ = ("_encoded",)

    def __init__(self, encoded: str) -> None:
        self._encoded = encoded

    def for_persistence(self) -> str:
        """Return the encoded verifier only for the credential persistence adapter."""
        return self._encoded

    def __repr__(self) -> str:
        return f"{type(self).__name__}({REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(REDACTED, format_spec)


class KeyedDigest:
    """A Restricted keyed digest whose output requires explicit persistence access."""

    __slots__ = ("_encoded",)

    def __init__(self, encoded: str) -> None:
        self._encoded = encoded

    def for_persistence(self) -> str:
        """Return the encoded digest only for persistence or constant-time comparison."""
        return self._encoded

    def __repr__(self) -> str:
        return f"{type(self).__name__}({REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return format(REDACTED, format_spec)
