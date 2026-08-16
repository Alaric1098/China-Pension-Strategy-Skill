"""Skill contract tests for SKILL.md, eval fixtures, and the golden case.

Covers: frontmatter, trigger coverage, privacy workflow, CLI commands, no
inline policy calculations, output handling, LOCAL_MVP constraint, disclaimer
behavior, eval manifest validity, and a golden case executed end-to-end
through analyze, stored JSON/manifest, and Markdown rendering.
"""

import importlib
import importlib.util
import inspect
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "SKILL.md"
EVALS_PATH = ROOT / "evals"
CLI = ["-m", "china_pension_strategy.entrypoints.cli.main"]

_EXPIRES_AFTER = "2027-01-01T00:00:00Z"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *CLI, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd or ROOT,
    )


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the leading ``---``-delimited YAML-ish block (key: value lines)."""
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with a --- delimited frontmatter block"
    frontmatter: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def test_frontmatter_declares_skill_name_and_description() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    assert frontmatter.get("name") == "china-pension-strategy"
    assert frontmatter.get("description")


def test_trigger_description_covers_mandatory_domains() -> None:
    frontmatter = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    description = frontmatter["description"].lower()
    for keyword in (
        "pension",
        "contribution",
        "retirement",
        "gap",
        "flexible",
        "subsidy",
        "regional",
        "strategy",
    ):
        assert keyword in description, f"trigger description misses {keyword!r}"


def test_trigger_description_covers_mandatory_chinese_domains() -> None:
    frontmatter = parse_frontmatter(SKILL_PATH.read_text(encoding="utf-8"))
    description = frontmatter["description"]
    for keyword in (
        "养老",
        "社保",
        "缴费",
        "缺口",
        "灵活就业",
        "补贴",
        "北京",
        "权益单",
    ):
        assert keyword in description, f"trigger description misses {keyword!r}"


def test_skill_documents_cli_commands() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    for command in ("validate", "analyze", "render", "cleanup"):
        assert command in text, f"SKILL.md must document the {command} command"


def test_skill_documents_privacy_workflow_before_analysis() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "REDACT" in text and "BLOCK" in text
    assert "身份证" in text and "社保" in text and "银行卡" in text
    assert re.search(r"先.*扫描|扫描.*(后|前).*分析|分析前", text), (
        "privacy scanning must be documented as happening before analysis"
    )


def test_skill_contains_no_inline_policy_calculations() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "%" not in text, "SKILL.md must not hardcode rates/percentages"
    assert "2/3" not in text, "SKILL.md must not hardcode the subsidy ratio"
    assert not re.search(r"\b\d+\.\d{2}\b", text), "SKILL.md must not hardcode money literals"


def test_skill_documents_output_handling() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "信封" in text or "envelope" in text
    assert "analysis-output" in text
    assert "analysis.json" in text and "manifest.json" in text


def test_skill_documents_local_mvp_constraint() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "LOCAL_MVP" in text
    assert "MVP_REVIEWED" in text
    assert "PRODUCTION" in text


def test_skill_contains_disclaimer() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "免责" in text
    assert "经办机构" in text
    assert "核验" in text


def test_skill_contains_no_sample_sensitive_identifiers() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\b\d{17}[0-9Xx]\b", text)
    assert not re.search(r"\d{3}-\d{2}-\d{4}", text)
    assert not re.search(r"\b1[3-9]\d{9}\b", text)
    assert "校验码：" not in text and "查询流水号：" not in text


def load_eval_manifest() -> dict:
    manifest = json.loads((EVALS_PATH / "evals.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0.0"
    return manifest


def test_eval_manifest_references_existing_fixtures() -> None:
    manifest = load_eval_manifest()
    cases = manifest["cases"]
    assert len(cases) >= 8
    for case in cases:
        fixture = EVALS_PATH / "fixtures" / case["fixture"]
        assert fixture.is_file(), f"eval fixture missing: {case['fixture']}"


def test_eval_cases_cover_required_modes() -> None:
    kinds = {case["kind"] for case in load_eval_manifest()["cases"]}
    assert {
        "success",
        "partial",
        "global_block",
        "record_conflict",
        "unknown_eligibility",
        "policy_version_miss",
        "replay",
    }.issubset(kinds)


def _fixture_paths() -> list[tuple[str, dict]]:
    return [(case["id"], case) for case in load_eval_manifest()["cases"]]


def test_eval_fixtures_produce_expected_exit_codes(tmp_path, monkeypatch) -> None:
    for case_id, case in _fixture_paths():
        runs_dir = tmp_path / f"runs-{case_id}"
        result = run_cli(
            "analyze",
            "--input",
            str(EVALS_PATH / "fixtures" / case["fixture"]),
            "--runs-dir",
            str(runs_dir),
        )
        assert result.returncode == case["expected_exit_code"], (
            f"{case_id}: expected exit {case['expected_exit_code']}, "
            f"got {result.returncode}: {result.stderr}"
        )


def test_privacy_block_fixture_produces_no_artifacts(tmp_path) -> None:
    block = next(case for case in load_eval_manifest()["cases"] if case["kind"] == "global_block")
    runs_dir = tmp_path / "runs"
    result = run_cli(
        "analyze",
        "--input",
        str(EVALS_PATH / "fixtures" / block["fixture"]),
        "--runs-dir",
        str(runs_dir),
    )
    assert result.returncode == 5
    assert not runs_dir.exists()


def test_privacy_redact_fixture_warns_and_never_leaks(tmp_path) -> None:
    redact = next(
        case for case in load_eval_manifest()["cases"] if case["kind"] == "privacy_redact"
    )
    runs_dir = tmp_path / "runs"
    result = run_cli(
        "analyze",
        "--input",
        str(EVALS_PATH / "fixtures" / redact["fixture"]),
        "--runs-dir",
        str(runs_dir),
    )
    assert result.returncode == 0
    envelope = json.loads(result.stdout)
    assert any("redacted" in warning["message"] for warning in envelope["warnings"])
    run_id = envelope["data"]["run_id"]
    stored = (runs_dir / run_id / "analysis.json").read_text(encoding="utf-8")
    assert redact["sensitive_value"] not in stored


def test_replay_fixture_yields_identical_run_id(tmp_path) -> None:
    manifest = load_eval_manifest()
    golden = next(case for case in manifest["cases"] if case["kind"] == "success")
    replay = next(case for case in manifest["cases"] if case["kind"] == "replay")
    runs_dir = tmp_path / "runs"
    run_ids = set()
    for case in (golden, replay):
        result = run_cli(
            "analyze",
            "--input",
            str(EVALS_PATH / "fixtures" / case["fixture"]),
            "--runs-dir",
            str(runs_dir),
        )
        assert result.returncode == 0
        run_ids.add(json.loads(result.stdout)["data"]["run_id"])
    assert len(run_ids) == 1


def test_golden_case_runs_through_analyze_render_and_cleanup(tmp_path: Path) -> None:
    manifest = load_eval_manifest()
    golden = next(case for case in manifest["cases"] if case["kind"] == "success")
    fixture = EVALS_PATH / "fixtures" / golden["fixture"]
    runs_dir = tmp_path / "runs"

    analyze = run_cli("analyze", "--input", str(fixture), "--runs-dir", str(runs_dir))
    assert analyze.returncode == 0, analyze.stderr
    envelope = json.loads(analyze.stdout)
    assert envelope["schema_version"] == "1.0.0"
    assert envelope["status"] == "success"
    assert envelope["errors"] == []
    assert envelope["data"]["status"] == "VALIDATED"
    run_id = envelope["data"]["run_id"]

    analysis_file = runs_dir / run_id / "analysis.json"
    manifest_file = runs_dir / run_id / "manifest.json"
    assert analysis_file.is_file()
    assert manifest_file.is_file()
    stored = json.loads(analysis_file.read_text(encoding="utf-8"))
    assert stored["schema_version"] == "2.0.0"
    assert stored["case_id"] == golden["case_id"]
    assert stored["recommendation"]["scenario_id"] == "continue"
    stored_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert stored_manifest["run_id"] == run_id
    assert stored_manifest["validation_status"] == "passed"

    markdown = run_cli(
        "render",
        "--run-id",
        run_id,
        "--runs-dir",
        str(runs_dir),
        "--format",
        "markdown",
    )
    assert markdown.returncode == 0, markdown.stderr
    assert run_id in markdown.stdout
    assert "## Recommendation" in markdown.stdout
    assert "## Scenario Comparison" in markdown.stdout

    rendered = run_cli(
        "render",
        "--run-id",
        run_id,
        "--runs-dir",
        str(runs_dir),
        "--format",
        "json",
    )
    assert rendered.returncode == 0, rendered.stderr
    re_envelope = json.loads(rendered.stdout)
    assert re_envelope["data"]["artifact_ref"] == f"runs/{run_id}/analysis.json"

    cleanup = run_cli(
        "cleanup",
        "--runs-dir",
        str(runs_dir),
        "--expires-before",
        _EXPIRES_AFTER,
    )
    assert cleanup.returncode == 0, cleanup.stderr
    assert not manifest_file.exists()
    deletion_manifests = list((runs_dir / "manifests").glob("deletion-*.json"))
    assert deletion_manifests


def test_ci_matrix_covers_all_declared_python_versions() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    for version in ('"3.12"', '"3.13"', '"3.14"'):
        assert version in workflow


def test_ci_has_reproducible_quality_gate() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    quality = set(project["project"]["optional-dependencies"]["quality"])
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert quality == {
        "mypy==2.3.1",
        "ruff==0.16.3",
        "types-jsonschema==4.26.0.20260518",
    }
    assert "name: Quality" in workflow
    assert 'python-version: "3.14"' in workflow
    assert 'python -m pip install -e ".[test,quality]"' in workflow
    assert "python -m ruff format --check ." in workflow
    assert "python -m ruff check ." in workflow
    assert "python -m mypy src/china_pension_strategy" in workflow


def test_policy_expiry_workflow_is_scheduled_and_actionable() -> None:
    workflow = (ROOT / ".github" / "workflows" / "policy-expiry.yml").read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "issues: write" in workflow
    assert "concurrency:" in workflow
    assert "automated-policy-expiry" in workflow
    assert "gh issue create" in workflow
    assert "gh issue close" in workflow
    assert "exit 1" in workflow


def test_package_release_and_engine_semantics_are_independently_versioned() -> None:
    spec = importlib.util.find_spec("china_pension_strategy.version")
    assert spec is not None, "version module must separate package and engine versions"
    versions = importlib.import_module("china_pension_strategy.version")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert versions.PACKAGE_VERSION == project["project"]["version"]
    assert versions.ENGINE_SEMANTICS_VERSION == "0.1.1"

    from china_pension_strategy.adapters.regions import create_region_adapter
    from china_pension_strategy.entrypoints.cli.main import _build_parser

    args = _build_parser().parse_args(["analyze", "--input", "input.json", "--runs-dir", "runs"])
    assert args.engine == versions.ENGINE_SEMANTICS_VERSION
    assert (
        inspect.signature(create_region_adapter).parameters["engine_version"].default
        == versions.ENGINE_SEMANTICS_VERSION
    )


_GOVERNANCE_FILES = (
    "SECURITY.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/policy_update.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/pull_request_template.md",
)


def test_public_governance_templates_are_complete() -> None:
    for rel in _GOVERNANCE_FILES:
        assert (ROOT / rel).is_file(), f"governance file missing: {rel}"

    issue_templates = _GOVERNANCE_FILES[1:4]
    for rel in issue_templates:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{rel} must start with YAML frontmatter"
        assert re.search(r"\n---\n", text), f"{rel} must close the YAML frontmatter block"
        frontmatter = text.split("---\n", 2)[1]
        fields = {line.split(":", 1)[0].strip() for line in frontmatter.splitlines() if ":" in line}
        for field in ("name", "about", "title", "labels", "assignees"):
            assert field in fields, f"{rel} frontmatter misses {field!r}"

    for rel in (*issue_templates, ".github/pull_request_template.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "- [ ]" in text, f"{rel} must default to unchecked confirmations"
        assert re.search(r"synthetic|合成", text, re.IGNORECASE), (
            f"{rel} must require synthetic data"
        )
        assert not re.search(r"\b\d{17}[0-9Xx]\b", text), f"{rel} must not show an ID number"
        assert not re.search(r"\b1[3-9]\d{9}\b", text), f"{rel} must not show a phone number"
        assert not re.search(r"\b\d{16,19}\b", text), f"{rel} must not show a card number"

    bug = (ROOT / issue_templates[0]).read_text(encoding="utf-8").lower()
    for keyword in ("reproduc", "region", "capabilit", "observed", "expected", "run_id"):
        assert keyword in bug, f"bug template misses {keyword!r}"

    policy = (ROOT / issue_templates[1]).read_text(encoding="utf-8").lower()
    for keyword in (
        "gov.cn",
        "authorit",
        "document number",
        "publication",
        "retrieval",
        "effective",
        "quot",
        "jurisdiction",
        "ruleset",
        "digest",
    ):
        assert keyword in policy, f"policy template misses {keyword!r}"

    feature = (ROOT / issue_templates[2]).read_text(encoding="utf-8").lower()
    for keyword in ("problem", "smallest", "scope", "region", "capabilit", "privacy", "semantic"):
        assert keyword in feature, f"feature template misses {keyword!r}"

    pr = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8").lower()
    for keyword in (
        "schema",
        "ruleset",
        "version",
        "run_id",
        "evidence",
        "privacy",
        "synthetic",
        "pytest",
        "ruff",
        "mypy",
    ):
        assert keyword in pr, f"PR template misses {keyword!r}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for link in ("SECURITY.md", "CONTRIBUTING.md", "issue-roadmap"):
        assert link in readme, f"README.md must link {link!r}"

    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert ".specify/memory/constitution.md" not in contributing, (
        "CONTRIBUTING.md must not require the internal constitution"
    )
