"""Canonical normalized-email identity validation."""

import re
import unicodedata
from typing import Final

_EMAIL_PATTERN: Final = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    """Return the documented NFKC, trimmed, lowercase login identifier."""
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    if len(normalized) > 320 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("INVALID_EMAIL")
    return normalized
