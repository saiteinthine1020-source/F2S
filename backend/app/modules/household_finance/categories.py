"""Finance-category validation, lifecycle, and authorization orchestration."""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.modules.household_finance.repositories import FinanceCategoryRecord, FinanceRepository
from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    Capability,
    require_capability,
)


class CategoryApplicability(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    BOTH = "BOTH"


class ActivityClassification(StrEnum):
    HOUSEHOLD = "HOUSEHOLD"
    FARM = "FARM"
    BUSINESS = "BUSINESS"


class DuplicateFinanceCategory(Exception):
    pass


class FinanceCategoryVersionMismatch(Exception):
    pass


class FinanceCategoryStateConflict(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CategoryName:
    display: str
    normalized: str


def normalize_category_name(value: str) -> CategoryName:
    if type(value) is not str:
        raise ValueError("INVALID_CATEGORY_NAME")
    display = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not 1 <= len(display) <= 128:
        raise ValueError("INVALID_CATEGORY_NAME")
    normalized = display.lower()
    if re.search(r"[\x00-\x1f\x7f]", normalized):
        raise ValueError("INVALID_CATEGORY_NAME")
    return CategoryName(display, normalized)


class FinanceCategoryService:
    def __init__(self, repository: FinanceRepository) -> None:
        self._repository = repository

    async def list_categories(
        self, context: AuthorizationContext, *, include_archived: bool = False
    ) -> tuple[FinanceCategoryRecord, ...]:
        require_capability(context, Capability.ACCESS_WORKSPACE)
        return await self._repository.list_categories(context, include_archived=include_archived)

    async def create(
        self,
        context: AuthorizationContext,
        *,
        name: str,
        applicability: CategoryApplicability,
        activity: ActivityClassification | None,
    ) -> FinanceCategoryRecord:
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        category_name = normalize_category_name(name)
        return await self._repository.create_category(
            context,
            display_name=category_name.display,
            normalized_name=category_name.normalized,
            applicability_code=applicability.value,
            activity_classification_code=activity.value if activity else None,
        )

    async def rename(
        self,
        context: AuthorizationContext,
        *,
        category_id: UUID,
        expected_version: int,
        name: str,
    ) -> FinanceCategoryRecord:
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        if expected_version <= 0:
            raise FinanceCategoryVersionMismatch
        category_name = normalize_category_name(name)
        return await self._repository.rename_category(
            context,
            category_id=category_id,
            expected_version=expected_version,
            display_name=category_name.display,
            normalized_name=category_name.normalized,
        )

    async def archive(
        self, context: AuthorizationContext, *, category_id: UUID, expected_version: int
    ) -> FinanceCategoryRecord:
        require_capability(context, Capability.MANAGE_FINANCE_CATEGORIES)
        if expected_version <= 0:
            raise FinanceCategoryVersionMismatch
        return await self._repository.archive_category(
            context, category_id=category_id, expected_version=expected_version
        )
