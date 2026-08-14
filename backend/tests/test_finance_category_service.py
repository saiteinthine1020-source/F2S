"""Finance-category policy, normalization, and lifecycle orchestration tests."""

import asyncio
from typing import cast
from uuid import uuid4

import pytest

from app.modules.household_finance import (
    ActivityClassification,
    CategoryApplicability,
    FinanceCategoryRecord,
    FinanceCategoryService,
    FinanceCategoryVersionMismatch,
    FinanceRepository,
    normalize_category_name,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)


class FakeFinanceRepository:
    def __init__(self) -> None:
        self.record = FinanceCategoryRecord(uuid4(), "Food", "EXPENSE", "HOUSEHOLD", "ACTIVE", 1)
        self.received: dict[str, object] = {}

    async def get_category(self, **values: object) -> FinanceCategoryRecord | None:
        raise AssertionError(values)

    async def get_event(self, **values: object) -> None:
        raise AssertionError(values)

    async def list_categories(
        self, context: AuthorizationContext, *, include_archived: bool
    ) -> tuple[FinanceCategoryRecord, ...]:
        self.received = {"context": context, "include_archived": include_archived}
        return (self.record,)

    async def create_category(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        self.received = {"context": context, **values}
        return self.record

    async def rename_category(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        self.received = {"context": context, **values}
        return self.record

    async def archive_category(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        self.received = {"context": context, **values}
        return self.record


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def test_category_name_normalization_is_stable_and_bounded() -> None:
    normalized = normalize_category_name("  \uff26\uff4f\uff4f\uff44\t Costs ")
    assert normalized.display == "Food Costs"
    assert normalized.normalized == "food costs"
    for value in ("", " ", "x" * 129, "Food\x00Cost"):
        with pytest.raises(ValueError, match="INVALID_CATEGORY_NAME"):
            normalize_category_name(value)


def test_all_roles_list_but_only_admin_mutates() -> None:
    async def exercise() -> None:
        for role in WorkspaceRole:
            repository = FakeFinanceRepository()
            service = FinanceCategoryService(cast(FinanceRepository, repository))
            assert await service.list_categories(_context(role)) == (repository.record,)

        for role in (WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR):
            repository = FakeFinanceRepository()
            service = FinanceCategoryService(cast(FinanceRepository, repository))
            with pytest.raises(AuthorizationDenied):
                await service.create(
                    _context(role),
                    name="Food",
                    applicability=CategoryApplicability.EXPENSE,
                    activity=ActivityClassification.HOUSEHOLD,
                )

        repository = FakeFinanceRepository()
        service = FinanceCategoryService(cast(FinanceRepository, repository))
        await service.create(
            _context(WorkspaceRole.ADMIN),
            name="  Food  Costs ",
            applicability=CategoryApplicability.EXPENSE,
            activity=ActivityClassification.HOUSEHOLD,
        )
        assert repository.received["display_name"] == "Food Costs"
        assert repository.received["normalized_name"] == "food costs"

    asyncio.run(exercise())


def test_mutations_require_a_positive_current_version() -> None:
    async def exercise() -> None:
        service = FinanceCategoryService(cast(FinanceRepository, FakeFinanceRepository()))
        context = _context(WorkspaceRole.ADMIN)
        for version in (0, -1):
            with pytest.raises(FinanceCategoryVersionMismatch):
                await service.rename(
                    context,
                    category_id=uuid4(),
                    expected_version=version,
                    name="Food",
                )
            with pytest.raises(FinanceCategoryVersionMismatch):
                await service.archive(
                    context,
                    category_id=uuid4(),
                    expected_version=version,
                )

    asyncio.run(exercise())
