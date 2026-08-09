"""Workspace settings merge, defaults, and validation tests."""

import asyncio
from typing import cast
from uuid import uuid4

import pytest

from app.modules.workspace_access import (
    AuthorizationContext,
    DesiredWorkspaceSettings,
    ModuleCode,
    ModuleSetting,
    WorkspaceAccessRepository,
    WorkspaceAdministration,
    WorkspaceModuleReference,
    WorkspaceReference,
    WorkspaceRole,
    WorkspaceSettingsPatch,
    WorkspaceSettingsService,
    WorkspaceSettingsSnapshot,
    WorkspaceType,
)


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.workspace = WorkspaceReference(
            id=uuid4(),
            name="Household",
            type_code="HOUSEHOLD",
            base_currency_code="USD",
            timezone="UTC",
            preferred_language="en",
            version=3,
        )
        self.administration = WorkspaceAdministration(
            id=self.workspace.id,
            description="Current",
            address=None,
            business_category_code=None,
            farm_type_code=None,
            version=3,
        )
        self.modules = tuple(
            WorkspaceModuleReference(uuid4(), code.value, code is ModuleCode.HOUSEHOLD_FINANCE, 1)
            for code in ModuleCode
        )
        self.desired: DesiredWorkspaceSettings | None = None

    async def resolve_context(self, **values: object) -> AuthorizationContext:
        raise AssertionError(values)

    async def get_workspace(self, context: object) -> WorkspaceReference:
        del context
        return self.workspace

    async def get_workspace_administration(self, context: object) -> WorkspaceAdministration:
        del context
        return self.administration

    async def list_modules(self, context: object) -> tuple[WorkspaceModuleReference, ...]:
        del context
        return self.modules

    async def set_module_enabled(self, **values: object) -> WorkspaceModuleReference:
        raise AssertionError(values)

    async def update_settings(
        self,
        context: object,
        *,
        expected_version: int,
        desired: DesiredWorkspaceSettings,
    ) -> WorkspaceSettingsSnapshot:
        del context
        assert expected_version == 3
        self.desired = desired
        return WorkspaceSettingsSnapshot(self.workspace, self.administration, self.modules)


def _admin(workspace_id: object) -> AuthorizationContext:
    from uuid import UUID

    assert isinstance(workspace_id, UUID)
    return AuthorizationContext(
        actor_account_id=uuid4(),
        workspace_id=workspace_id,
        membership_id=uuid4(),
        role=WorkspaceRole.ADMIN,
        correlation_id=uuid4(),
    )


def test_type_change_preserves_explicit_modules_and_validates_profile() -> None:
    async def exercise() -> None:
        repository = FakeWorkspaceRepository()
        service = WorkspaceSettingsService(cast(WorkspaceAccessRepository, repository))
        await service.update(
            _admin(repository.workspace.id),
            expected_version=3,
            patch=WorkspaceSettingsPatch(
                provided=frozenset({"workspace_type", "farm_type_code", "modules"}),
                workspace_type=WorkspaceType.FARM,
                farm_type_code="rice_farm",
                modules=(ModuleSetting(ModuleCode.FARMING_INVESTMENTS, True),),
            ),
        )
        assert repository.desired is not None
        assert repository.desired.workspace_type is WorkspaceType.FARM
        assert repository.desired.farm_type_code == "RICE_FARM"
        assert dict(repository.desired.modules) == {
            ModuleCode.FARMING_INVESTMENTS: True,
            ModuleCode.HOUSEHOLD_FINANCE: True,
        }

        with pytest.raises(ValueError, match="BUSINESS_CATEGORY_NOT_APPLICABLE"):
            await service.update(
                _admin(repository.workspace.id),
                expected_version=3,
                patch=WorkspaceSettingsPatch(
                    provided=frozenset({"business_category_code"}),
                    business_category_code="retail",
                ),
            )

    asyncio.run(exercise())


def test_duplicate_module_updates_and_empty_patch_are_rejected() -> None:
    async def exercise() -> None:
        repository = FakeWorkspaceRepository()
        service = WorkspaceSettingsService(cast(WorkspaceAccessRepository, repository))
        context = _admin(repository.workspace.id)
        with pytest.raises(ValueError, match="EMPTY_SETTINGS_PATCH"):
            await service.update(
                context,
                expected_version=3,
                patch=WorkspaceSettingsPatch(provided=frozenset()),
            )
        with pytest.raises(ValueError, match="DUPLICATE_MODULE_CODE"):
            await service.update(
                context,
                expected_version=3,
                patch=WorkspaceSettingsPatch(
                    provided=frozenset({"modules"}),
                    modules=(
                        ModuleSetting(ModuleCode.HOUSEHOLD_FINANCE, True),
                        ModuleSetting(ModuleCode.HOUSEHOLD_FINANCE, False),
                    ),
                ),
            )

    asyncio.run(exercise())
