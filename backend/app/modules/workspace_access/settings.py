"""Workspace retrieval and validated optimistic settings orchestration."""

from dataclasses import dataclass

from app.modules.workspace_access.authorization import AuthorizationContext, Capability
from app.modules.workspace_access.configuration import (
    ModuleCode,
    WorkspaceType,
    bounded_text,
    optional_profile_code,
    optional_text,
    validate_currency,
    validate_language,
    validate_profile_combination,
    validate_timezone,
)
from app.modules.workspace_access.repositories import (
    DesiredWorkspaceSettings,
    WorkspaceAccessRepository,
    WorkspaceAdministration,
    WorkspaceModuleReference,
    WorkspaceReference,
    WorkspaceSettingsSnapshot,
)


@dataclass(frozen=True, slots=True)
class ModuleSetting:
    module_code: ModuleCode
    enabled: bool


@dataclass(frozen=True, slots=True)
class WorkspaceSettingsPatch:
    provided: frozenset[str]
    name: str | None = None
    workspace_type: WorkspaceType | None = None
    base_currency_code: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None
    description: str | None = None
    address: str | None = None
    business_category_code: str | None = None
    farm_type_code: str | None = None
    modules: tuple[ModuleSetting, ...] | None = None


@dataclass(frozen=True, slots=True)
class SelectedWorkspace:
    workspace: WorkspaceReference
    modules: tuple[WorkspaceModuleReference, ...]
    administration: WorkspaceAdministration | None


class WorkspaceSettingsService:
    def __init__(self, repository: WorkspaceAccessRepository) -> None:
        self._repository = repository

    async def get_selected(self, context: AuthorizationContext) -> SelectedWorkspace:
        workspace = await self._repository.get_workspace(context)
        modules = await self._repository.list_modules(context)
        administration = (
            await self._repository.get_workspace_administration(context)
            if context.permits(Capability.MANAGE_WORKSPACE_SETTINGS)
            else None
        )
        return SelectedWorkspace(workspace, modules, administration)

    async def update(
        self,
        context: AuthorizationContext,
        *,
        expected_version: int,
        patch: WorkspaceSettingsPatch,
    ) -> WorkspaceSettingsSnapshot:
        if expected_version <= 0:
            raise ValueError("INVALID_VERSION")
        if not patch.provided:
            raise ValueError("EMPTY_SETTINGS_PATCH")
        current_workspace = await self._repository.get_workspace(context)
        current_administration = await self._repository.get_workspace_administration(context)
        current_modules = await self._repository.list_modules(context)

        workspace_type = (
            _required(patch.workspace_type, "INVALID_WORKSPACE_TYPE")
            if "workspace_type" in patch.provided
            else WorkspaceType(current_workspace.type_code)
        )
        name = (
            bounded_text(
                _required(patch.name, "INVALID_WORKSPACE_NAME"),
                maximum=160,
                code="INVALID_WORKSPACE_NAME",
            )
            if "name" in patch.provided
            else current_workspace.name
        )
        currency = (
            validate_currency(_required(patch.base_currency_code, "INVALID_CURRENCY"))
            if "base_currency_code" in patch.provided
            else current_workspace.base_currency_code
        )
        timezone = (
            validate_timezone(_required(patch.timezone, "INVALID_TIMEZONE"))
            if "timezone" in patch.provided
            else current_workspace.timezone
        )
        language = (
            validate_language(_required(patch.preferred_language, "INVALID_LANGUAGE"))
            if "preferred_language" in patch.provided
            else current_workspace.preferred_language
        )
        description = (
            optional_text(patch.description, maximum=2000, code="INVALID_DESCRIPTION")
            if "description" in patch.provided
            else current_administration.description
        )
        address = (
            optional_text(patch.address, maximum=1000, code="INVALID_ADDRESS")
            if "address" in patch.provided
            else current_administration.address
        )
        business_category = (
            optional_profile_code(patch.business_category_code, code="INVALID_BUSINESS_CATEGORY")
            if "business_category_code" in patch.provided
            else current_administration.business_category_code
        )
        farm_type = (
            optional_profile_code(patch.farm_type_code, code="INVALID_FARM_TYPE")
            if "farm_type_code" in patch.provided
            else current_administration.farm_type_code
        )
        validate_profile_combination(workspace_type, business_category, farm_type)

        modules = {ModuleCode(item.module_code): item.enabled for item in current_modules}
        if set(modules) != set(ModuleCode):
            raise ValueError("INCOMPLETE_MODULE_CONFIGURATION")
        if patch.modules is not None:
            updates = [setting.module_code for setting in patch.modules]
            if len(updates) != len(set(updates)):
                raise ValueError("DUPLICATE_MODULE_CODE")
            modules.update({setting.module_code: setting.enabled for setting in patch.modules})
        desired = DesiredWorkspaceSettings(
            name=name,
            workspace_type=workspace_type,
            base_currency_code=currency,
            timezone=timezone,
            preferred_language=language,
            description=description,
            address=address,
            business_category_code=business_category,
            farm_type_code=farm_type,
            modules=tuple(sorted(modules.items(), key=lambda item: item[0].value)),
        )
        return await self._repository.update_settings(
            context,
            expected_version=expected_version,
            desired=desired,
        )


def _required[T](value: T | None, code: str) -> T:
    if value is None:
        raise ValueError(code)
    return value
