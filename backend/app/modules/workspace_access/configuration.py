"""Canonical workspace type, module, and settings validation."""

import re
import unicodedata
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CURRENCY_PATTERN: Final = re.compile(r"^[A-Z]{3}$")
_PROFILE_CODE_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
SUPPORTED_LANGUAGES: Final = frozenset({"en", "ja", "my", "shn"})


class WorkspaceType(StrEnum):
    HOUSEHOLD = "HOUSEHOLD"
    FARM = "FARM"
    MICROBUSINESS = "MICROBUSINESS"
    SMALL_BUSINESS = "SMALL_BUSINESS"
    COMBINED = "COMBINED"
    CUSTOM = "CUSTOM"


class ModuleCode(StrEnum):
    HOUSEHOLD_FINANCE = "HOUSEHOLD_FINANCE"
    FARMING_INVESTMENTS = "FARMING_INVESTMENTS"


MODULE_DEFAULTS: Final = {
    WorkspaceType.HOUSEHOLD: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.FARM: frozenset({ModuleCode.HOUSEHOLD_FINANCE, ModuleCode.FARMING_INVESTMENTS}),
    WorkspaceType.MICROBUSINESS: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.SMALL_BUSINESS: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.COMBINED: frozenset(
        {ModuleCode.HOUSEHOLD_FINANCE, ModuleCode.FARMING_INVESTMENTS}
    ),
    WorkspaceType.CUSTOM: frozenset(),
}


def validate_currency(value: str) -> str:
    if not _CURRENCY_PATTERN.fullmatch(value):
        raise ValueError("INVALID_CURRENCY")
    return value


def validate_language(value: str) -> str:
    if value not in SUPPORTED_LANGUAGES:
        raise ValueError("INVALID_LANGUAGE")
    return value


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("INVALID_TIMEZONE") from error
    return value


def bounded_text(value: str, *, maximum: int, code: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(code)
    return normalized


def optional_text(value: str | None, *, maximum: int, code: str) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise ValueError(code)
    return normalized


def optional_profile_code(value: str | None, *, code: str) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    if not _PROFILE_CODE_PATTERN.fullmatch(normalized):
        raise ValueError(code)
    return normalized


def validate_profile_combination(
    workspace_type: WorkspaceType,
    business_category_code: str | None,
    farm_type_code: str | None,
) -> None:
    business_types = {
        WorkspaceType.MICROBUSINESS,
        WorkspaceType.SMALL_BUSINESS,
        WorkspaceType.COMBINED,
        WorkspaceType.CUSTOM,
    }
    farm_types = {WorkspaceType.FARM, WorkspaceType.COMBINED, WorkspaceType.CUSTOM}
    if business_category_code is not None and workspace_type not in business_types:
        raise ValueError("BUSINESS_CATEGORY_NOT_APPLICABLE")
    if farm_type_code is not None and workspace_type not in farm_types:
        raise ValueError("FARM_TYPE_NOT_APPLICABLE")
