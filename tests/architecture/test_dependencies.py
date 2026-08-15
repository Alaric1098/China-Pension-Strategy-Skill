import ast
import importlib
import importlib.util
from pathlib import Path


PACKAGE_NAME = "china_pension_strategy"
FORBIDDEN_DOMAIN_LAYERS = {"application", "ports", "adapters", "entrypoints"}
FORBIDDEN_APPLICATION_LAYERS = {"adapters", "entrypoints"}
FORBIDDEN_PORT_LAYERS = {"adapters", "entrypoints"}
ALLOWED_DOMAIN_DEPENDENCIES = {
    "__future__",
    "china_pension_strategy",
    "collections",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "hashlib",
    "itertools",
    "json",
    "math",
    "operator",
    "re",
    "typing",
}
FORBIDDEN_INFRASTRUCTURE_DEPENDENCIES = {
    "anthropic",
    "boto3",
    "botocore",
    "openai",
    "psycopg",
    "pymongo",
    "redis",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "subprocess",
}
def _imported_modules(tree: ast.AST) -> set[str]:
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                imported.update(alias.name for alias in node.names)
    return imported


def _dependency_violations(
    package_root: Path, source_layers: set[str] | None = None
) -> list[str]:
    violations = []
    forbidden_layers = {
        "domain": FORBIDDEN_DOMAIN_LAYERS,
        "application": FORBIDDEN_APPLICATION_LAYERS,
        "ports": FORBIDDEN_PORT_LAYERS,
    }

    for source_path in sorted(package_root.rglob("*.py")):
        relative_module = source_path.relative_to(package_root).with_suffix("")
        module_parts = list(relative_module.parts)
        if module_parts[-1] == "__init__":
            module_parts.pop()
        if not module_parts:
            continue
        source_layer = module_parts[0]
        if source_layer not in forbidden_layers or (
            source_layers is not None and source_layer not in source_layers
        ):
            continue

        module_name = ".".join((PACKAGE_NAME, *module_parts))
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"), filename=str(source_path)
        )
        for imported in sorted(_imported_modules(tree)):
            imported_parts = imported.split(".")
            root = imported_parts[0]
            imported_layer = (
                imported_parts[1]
                if root == PACKAGE_NAME and len(imported_parts) > 1
                else root
            )
            imports_outward_layer = imported_layer in forbidden_layers[source_layer]
            imports_forbidden_dependency = (
                source_layer == "domain"
                and root not in ALLOWED_DOMAIN_DEPENDENCIES
            ) or (
                source_layer != "domain"
                and root in FORBIDDEN_INFRASTRUCTURE_DEPENDENCIES
            )
            if imports_outward_layer or imports_forbidden_dependency:
                violations.append(f"{module_name} imports {imported}")

    return violations


def _check_domain_dependencies() -> None:
    package_spec = importlib.util.find_spec(PACKAGE_NAME)
    assert package_spec is not None, f"{PACKAGE_NAME} package is not installed"
    assert package_spec.submodule_search_locations is not None

    violations = []
    for package_location in package_spec.submodule_search_locations:
        violations.extend(
            _dependency_violations(Path(package_location), source_layers={"domain"})
        )

    assert not violations, "Forbidden domain dependencies:\n" + "\n".join(violations)


def test_domain_has_no_outward_dependencies() -> None:
    _check_domain_dependencies()


def test_dependency_scan_does_not_import_source_modules(monkeypatch) -> None:
    def fail_on_import(module_name: str):
        raise AssertionError(f"architecture scan imported {module_name}")

    monkeypatch.setattr(importlib, "import_module", fail_on_import)

    _check_domain_dependencies()


def test_static_scan_finds_outward_application_and_port_imports(tmp_path) -> None:
    package_root = tmp_path / PACKAGE_NAME
    application = package_root / "application"
    ports = package_root / "ports"
    application.mkdir(parents=True)
    ports.mkdir()
    (application / "use_case.py").write_text(
        "from china_pension_strategy.adapters.store import Repository\n",
        encoding="utf-8",
    )
    (ports / "repository.py").write_text(
        "from china_pension_strategy.entrypoints.cli import main\n",
        encoding="utf-8",
    )

    violations = _dependency_violations(package_root)

    assert violations == [
        "china_pension_strategy.application.use_case imports "
        "china_pension_strategy.adapters.store",
        "china_pension_strategy.application.use_case imports "
        "china_pension_strategy.adapters.store.Repository",
        "china_pension_strategy.ports.repository imports "
        "china_pension_strategy.entrypoints.cli",
        "china_pension_strategy.ports.repository imports "
        "china_pension_strategy.entrypoints.cli.main",
    ]


def test_static_scan_finds_database_process_network_and_sdk_imports(tmp_path) -> None:
    package_root = tmp_path / PACKAGE_NAME
    domain = package_root / "domain"
    domain.mkdir(parents=True)
    dependencies = [
        "anthropic",
        "boto3",
        "openai",
        "psycopg",
        "pymongo",
        "redis",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
    ]
    (domain / "service.py").write_text(
        "".join(f"import {dependency}\n" for dependency in dependencies),
        encoding="utf-8",
    )

    violations = _dependency_violations(package_root)

    assert violations == [
        f"china_pension_strategy.domain.service imports {dependency}"
        for dependency in dependencies
    ]


def test_domain_scan_allows_only_explicit_pure_dependencies(tmp_path) -> None:
    package_root = tmp_path / PACKAGE_NAME
    domain = package_root / "domain"
    domain.mkdir(parents=True)
    allowed = sorted(ALLOWED_DOMAIN_DEPENDENCIES)
    forbidden = ["asyncpg", "duckdb", "google.generativeai"]
    (domain / "service.py").write_text(
        "".join(f"import {dependency}\n" for dependency in (*allowed, *forbidden)),
        encoding="utf-8",
    )

    violations = _dependency_violations(package_root)

    assert violations == [
        "china_pension_strategy.domain.service imports asyncpg",
        "china_pension_strategy.domain.service imports duckdb",
        "china_pension_strategy.domain.service imports google.generativeai",
    ]


def test_application_and_ports_have_no_outward_dependencies() -> None:
    package_spec = importlib.util.find_spec(PACKAGE_NAME)
    assert package_spec is not None, f"{PACKAGE_NAME} package is not installed"
    assert package_spec.submodule_search_locations is not None

    violations = []
    for package_location in package_spec.submodule_search_locations:
        violations.extend(_dependency_violations(Path(package_location)))

    assert not violations, "Forbidden outward dependencies:\n" + "\n".join(violations)
