"""Region routing tests: schema, factory, and CLI behavior."""

import json
import subprocess
import sys
from datetime import UTC
from pathlib import Path

import jsonschema
import pytest

from china_pension_strategy.adapters.regions import (
    create_region_adapter,
)
from china_pension_strategy.adapters.regions.beijing import (
    BeijingRegionAdapter,
    RegionMappingError,
)
from china_pension_strategy.adapters.regions.chengdu import ChengduRegionAdapter
from china_pension_strategy.adapters.regions.chongqing import ChongqingRegionAdapter
from china_pension_strategy.adapters.regions.guangzhou import GuangzhouRegionAdapter
from china_pension_strategy.adapters.regions.hangzhou import HangzhouRegionAdapter
from china_pension_strategy.adapters.regions.nanjing import NanjingRegionAdapter
from china_pension_strategy.adapters.regions.shanghai import ShanghaiRegionAdapter
from china_pension_strategy.adapters.regions.shenzhen import ShenzhenRegionAdapter
from china_pension_strategy.adapters.regions.tianjin import TianjinRegionAdapter
from china_pension_strategy.adapters.regions.wuhan import WuhanRegionAdapter

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "person-input.schema.json"
GOLDEN = ROOT / "evals" / "fixtures" / "golden-beijing-flex-2026.json"
CLI = [sys.executable, "-m", "china_pension_strategy.entrypoints.cli.main"]


def load_golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def validate_person_input(record: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(record, schema)


def test_schema_accepts_each_region_value() -> None:
    for region in (
        "beijing",
        "shanghai",
        "guangzhou",
        "shenzhen",
        "hangzhou",
        "chengdu",
        "wuhan",
        "nanjing",
        "tianjin",
        "chongqing",
    ):
        record = load_golden()
        record["region"] = region
        validate_person_input(record)  # must not raise


def test_schema_region_defaults_to_beijing() -> None:
    record = load_golden()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    prop = schema["properties"]["region"]
    assert prop.get("default") == "beijing"
    assert "region" not in schema.get("required", [])
    validate_person_input(record)  # no region key -> still valid


def test_schema_rejects_unknown_region() -> None:
    record = load_golden()
    record["region"] = "xian"
    with pytest.raises(jsonschema.ValidationError):
        validate_person_input(record)


def test_factory_returns_beijing_adapter() -> None:
    adapter = create_region_adapter("beijing")
    assert isinstance(adapter, BeijingRegionAdapter)


def test_factory_returns_each_city_adapter() -> None:
    expected = {
        "shanghai": ShanghaiRegionAdapter,
        "guangzhou": GuangzhouRegionAdapter,
        "shenzhen": ShenzhenRegionAdapter,
        "hangzhou": HangzhouRegionAdapter,
        "chengdu": ChengduRegionAdapter,
        "wuhan": WuhanRegionAdapter,
        "nanjing": NanjingRegionAdapter,
        "tianjin": TianjinRegionAdapter,
        "chongqing": ChongqingRegionAdapter,
    }
    for region, adapter_type in expected.items():
        adapter = create_region_adapter(region)
        assert isinstance(adapter, adapter_type)


def test_factory_unknown_region_raises() -> None:
    with pytest.raises(RegionMappingError) as exc:
        create_region_adapter("xian")
    assert exc.value.code == "REGION_UNKNOWN"


def test_province_layer_query_structure() -> None:
    """Province-tier cities query CN (national), CN-XX (province contribution),
    and CN-XXXX (city subsidy); municipalities collapse province and city."""
    from datetime import date, datetime

    from china_pension_strategy.domain.policy import AnalysisMode

    as_of = date(2026, 8, 11)
    known = datetime(2026, 8, 11, 12, tzinfo=UTC)
    mode = AnalysisMode("LOCAL_MVP")

    layered = {
        "hangzhou": ("CN-33", "CN-3301"),
        "chengdu": ("CN-51", "CN-5101"),
        "wuhan": ("CN-42", "CN-4201"),
        "nanjing": ("CN-32", "CN-3201"),
    }
    for region, (prov, city) in layered.items():
        queries = create_region_adapter(region).policy_queries(
            as_of_effective_date=as_of, as_known_at=known, analysis_mode=mode
        )
        contribution_jurisdictions = {
            q.jurisdiction for q in queries if q.topic == "flexible_employment_contribution"
        }
        assert {q.topic: q.jurisdiction for q in queries}["minimum_contribution"] == "CN"
        # province tier carries pension contribution (CN-XX) and the city layer
        # carries municipal medical contribution (CN-XXXX)
        assert contribution_jurisdictions == {prov, city}
        assert {q.topic: q.jurisdiction for q in queries}["flexible_employment_subsidy"] == city

    for region, jur in (("tianjin", "CN-12"), ("chongqing", "CN-50")):
        queries = create_region_adapter(region).policy_queries(
            as_of_effective_date=as_of, as_known_at=known, analysis_mode=mode
        )
        by_topic = {q.topic: q.jurisdiction for q in queries}
        assert by_topic["minimum_contribution"] == "CN"
        assert by_topic["flexible_employment_contribution"] == jur
        assert by_topic["flexible_employment_subsidy"] == jur


def test_cli_beijing_region_keeps_golden_run_id(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    record = load_golden()
    record["region"] = "beijing"
    input_file = tmp_path / "input-beijing.json"
    input_file.write_text(json.dumps(record), encoding="utf-8")
    result = subprocess.run(
        [*CLI, "analyze", "--input", str(input_file), "--runs-dir", str(runs_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "success"
    # Content-addressed: same facts + same region default must reproduce the
    # golden run id even though the input now carries an explicit region key.
    assert (
        envelope["data"]["run_id"]
        == "run-95e2c71f61a9b8510cc4097e9c930d53afb36a4892be154802ac96c4687731e9"
    )


def test_cli_unknown_region_fails_cleanly(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    record = load_golden()
    record["region"] = "xian"
    input_file = tmp_path / "input-xian.json"
    input_file.write_text(json.dumps(record), encoding="utf-8")
    result = subprocess.run(
        [*CLI, "analyze", "--input", str(input_file), "--runs-dir", str(runs_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 3, result.stderr
    assert "INPUT_SCHEMA_INVALID" in result.stderr
