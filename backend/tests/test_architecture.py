"""Executable baseline for ADR-001 inward dependency rules."""

import ast
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "app" / "modules"
SHARED_KERNEL_ROOT = Path(__file__).parents[1] / "app" / "shared_kernel"
SCOPED_REPOSITORY_PATHS = (
    MODULE_ROOT / "workspace_access" / "repositories.py",
    Path(__file__).parents[1]
    / "app"
    / "infrastructure"
    / "database"
    / "repositories"
    / "workspace_access.py",
)
FORBIDDEN_IMPORTS = ("app.api", "fastapi", "sqlalchemy")
SHARED_KERNEL_FORBIDDEN_IMPORTS = FORBIDDEN_IMPORTS + (
    "app.infrastructure",
    "app.modules",
    "pydantic",
)


def imported_modules(path: Path) -> set[str]:
    """Return absolute import targets from a Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_business_modules_do_not_depend_on_http_or_persistence_frameworks() -> None:
    """Keep future module internals independent of outer frameworks."""
    violations: list[str] = []
    for source_path in MODULE_ROOT.rglob("*.py"):
        for imported in imported_modules(source_path):
            if imported.startswith(FORBIDDEN_IMPORTS):
                violations.append(f"{source_path}: {imported}")

    assert violations == []


def test_shared_kernel_has_no_outward_framework_or_module_dependencies() -> None:
    """Keep shared primitives stable, framework-free, and workflow-free."""
    assert SHARED_KERNEL_ROOT.is_dir()
    violations: list[str] = []
    for source_path in SHARED_KERNEL_ROOT.rglob("*.py"):
        for imported in imported_modules(source_path):
            if imported.startswith(SHARED_KERNEL_FORBIDDEN_IMPORTS):
                violations.append(f"{source_path}: {imported}")
    assert violations == []


def test_authoritative_shared_numeric_paths_do_not_use_binary_float() -> None:
    """Reject float literals, types, constructors, and Decimal.from_float calls."""
    violations: list[str] = []
    for source_path in SHARED_KERNEL_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            reason: str | None = None
            if isinstance(node, ast.Constant) and type(node.value) is float:
                reason = "float literal"
            elif isinstance(node, ast.Name) and node.id == "float":
                reason = "float type or constructor"
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Decimal"
                and node.attr == "from_float"
            ):
                reason = "Decimal.from_float"
            if reason is not None:
                violations.append(f"{source_path}:{getattr(node, 'lineno', 0)}: {reason}")
    assert violations == []


def test_protected_workspace_repository_methods_require_context() -> None:
    """Prevent a new public protected repository method from omitting authority."""
    violations: list[str] = []
    for repository_path in SCOPED_REPOSITORY_PATHS:
        tree = ast.parse(
            repository_path.read_text(encoding="utf-8"),
            filename=str(repository_path),
        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") or node.name == "resolve_context":
                continue
            positional_names = [argument.arg for argument in node.args.args]
            if positional_names[:2] != ["self", "context"]:
                violations.append(f"{repository_path.name}:{node.name}")

    assert violations == []
