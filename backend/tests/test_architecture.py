"""Executable baseline for ADR-001 inward dependency rules."""

import ast
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "app" / "modules"
FORBIDDEN_IMPORTS = ("app.api", "fastapi", "sqlalchemy")


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
