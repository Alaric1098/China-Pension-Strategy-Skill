"""Contracts for the bundled-data root used by loaders and renderers."""

import tomllib
from pathlib import Path

import pytest

from china_pension_strategy.adapters.data_root import data_root

ROOT = Path(__file__).resolve().parents[2]

_DATA_FILES = (
    "schemas",
    "policy-data",
    "policy-data/packages",
    "policy-data/sources",
)


def test_data_root_resolves_the_repository_root() -> None:
    root = data_root()
    assert (root / "schemas" / "person-input.schema.json").is_file()
    assert (root / "policy-data" / "packages").is_dir()
    assert root == ROOT


def test_data_root_honors_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHINA_PENSION_DATA_ROOT", str(ROOT))
    assert data_root() == ROOT


def test_pyproject_bundles_every_bundled_data_file() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    data_files = project["tool"]["setuptools"]["data-files"]
    declared: set[str] = set()
    for install_location, patterns in data_files.items():
        assert install_location.startswith("share/china-pension-strategy/")
        for pattern in patterns:
            declared.update(str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.glob(pattern))
    actual: set[str] = set()
    for directory in _DATA_FILES:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file():
                actual.add(str(path.relative_to(ROOT)).replace("\\", "/"))
    assert declared == actual, (
        f"data-files must bundle exactly the bundled data; missing: "
        f"{sorted(actual - declared)}, extra: {sorted(declared - actual)}"
    )
