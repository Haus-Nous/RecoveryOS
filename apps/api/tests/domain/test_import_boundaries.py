"""Tests verifying strict architectural framework and provider independence for domain layer."""

import ast
from pathlib import Path

FORBIDDEN_IMPORTS = frozenset(
    {
        "sqlalchemy",
        "fastapi",
        "redis",
        "asyncpg",
        "starlette",
        "pydantic",
        "httpx",
        "requests",
        "razorpay",
        "stripe",
        "adyen",
        "paypal",
        "cashfree",
    }
)

DOMAIN_DIR = Path(__file__).parent.parent.parent / "app" / "domain"


def get_imported_modules(file_path: Path) -> set[str]:
    """Parse a Python source file using AST and collect all root imported module names."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0].lower())
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0].lower())
    return modules


def test_domain_layer_has_zero_framework_or_provider_dependencies() -> None:
    """CRITICAL: Domain must be 100% pure Python without ORM/API/PSP coupling."""
    domain_files = list(DOMAIN_DIR.rglob("*.py"))
    assert len(domain_files) > 0, "Domain directory should contain Python files"

    violations: dict[str, set[str]] = {}
    for py_file in domain_files:
        imported = get_imported_modules(py_file)
        forbidden_found = imported.intersection(FORBIDDEN_IMPORTS)
        if forbidden_found:
            rel_path = py_file.relative_to(DOMAIN_DIR.parent.parent)
            violations[str(rel_path)] = forbidden_found

    assert not violations, f"Forbidden dependencies found in domain layer: {violations}"
