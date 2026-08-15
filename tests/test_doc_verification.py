"""Doc-verifier sensitive-scan tests.

The verifier must not flag *mentioning a field name* (inside backticks or
in odd-nesting residue) as a leak, while still catching real value-shaped
sensitive identifiers outside code markup.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "verify_design_docs.py"

spec = importlib.util.spec_from_file_location("verify_design_docs", VERIFIER)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

scan_sensitive = module.scan_sensitive
SENSITIVE_PATTERN = module.SENSITIVE_PATTERN


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Meta mentions of field names inside code spans are documentation.
        ("`校验码：` and `查询流水号：` are forbidden", []),
        ("`社会保障号码：` must never appear", []),
        # Odd-nesting backtick residue (double-backtick wraps single-backtick
        # spans) must also stay clean.
        ("`字符串 `校验码：` 与 `查询流水号：``", []),
        # Double-backtick nested mention.
        ("`` `校验码：` ``", []),
        # Real value-shaped identifiers outside code markup must hit.
        ("校验码：A1B2C3", ["校验码：A1B2C3"]),
        ("社会保障号码：110105199001011234", ["社会保障号码：110105199001011234"]),
        ("id 110105199001011234 end", ["110105199001011234"]),
        ("id 11010519900101123X end", ["11010519900101123X"]),
        # A label followed by another label word is not a leak.
        ("写了 校验码： 查询流水号： 段落", []),
        # Short values are not value-shaped enough.
        ("校验码：AB", []),
    ],
)
def test_scan_sensitive(text: str, expected: list[str]) -> None:
    assert scan_sensitive(text) == expected


def test_whole_repo_markdown_is_clean() -> None:
    """No real sensitive identifier anywhere in tracked Markdown."""
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "SKILL.md"]
    docs = ROOT / "docs"
    if docs.exists():
        files.extend(sorted(docs.rglob("*.md")))
    for path in files:
        assert scan_sensitive(path.read_text(encoding="utf-8")) == [], (
            f"sensitive match in {path.relative_to(ROOT)}"
        )


def test_verifier_exits_zero() -> None:
    """The doc-verifier gate passes (exit code 0)."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(VERIFIER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-500:]
