import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def corpus() -> str:
    files = [ROOT / "README.md"]
    docs = ROOT / "docs"
    if docs.exists():
        files.extend(sorted(docs.rglob("*.md")))
        files.extend(sorted(docs.rglob("*.json")))
    return "\n".join(path.read_text(encoding="utf-8") for path in files if path.exists())


def load_output_schema() -> dict[str, object]:
    path = ROOT / "docs" / "schemas" / "analysis-output.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def structural_checks() -> list[dict[str, object]]:
    schema = load_output_schema()
    properties = schema.get("properties", {})
    definitions = schema.get("$defs", {})
    eligibility = definitions.get("eligibilityAssessment", {})
    capability = definitions.get("capabilityAssessment", {})
    assumption = definitions.get("assumption", {})
    required = set(schema.get("required", []))
    snapshot_required = set(properties.get("snapshot", {}).get("required", []))
    reliability = (ROOT / "docs" / "computation-and-reliability.md").read_text(encoding="utf-8")
    privacy = (ROOT / "docs" / "security-and-privacy.md").read_text(encoding="utf-8")
    release = (ROOT / "docs" / "release-governance.md").read_text(encoding="utf-8")

    return [
        {
            "id": "output_schema_contract",
            "description": "输出schema包含权威契约集合",
            "passed": {
                "capabilities",
                "eligibility_assessments",
                "record_conflicts",
                "policy_ambiguities",
                "assumptions",
            }.issubset(required)
            and properties.get("status", {}).get("enum") == ["success", "partial"],
            "assertions": ["required collections", "analysis status excludes global error"],
        },
        {
            "id": "eligibility_capability_contract",
            "description": "资格与能力状态是封闭枚举",
            "passed": eligibility.get("properties", {}).get("status", {}).get("enum")
            == ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]
            and bool(eligibility.get("allOf"))
            and capability.get("properties", {}).get("status", {}).get("enum")
            == ["AVAILABLE", "PARTIAL", "BLOCKED"],
            "assertions": ["eligibility enum and condition derivation", "capability enum"],
        },
        {
            "id": "probability_evidence_contract",
            "description": "证据概率具有来源与完整性约束",
            "passed": {
                "event_definition",
                "source_date",
                "population",
                "provenance_refs",
                "approved_by",
                "expires_at",
                "dependency_treatment",
            }.issubset(set(assumption.get("required", [])))
            and "distribution" in assumption.get("properties", {})
            and bool(assumption.get("oneOf"))
            and assumption.get("properties", {}).get("provenance_refs", {}).get("minItems") == 1
            and all(
                token in json.dumps(assumption, ensure_ascii=False)
                for token in (
                    '"const": "EVIDENCE_BACKED_PROBABILITY"',
                    '"const": "official_statistic"',
                    '"approved_by"',
                    '"expires_at"',
                )
            ),
            "assertions": [
                "event definition",
                "official source pairing",
                "approval and expiry",
                "value shape",
            ],
        },
        {
            "id": "dual_time_identity_contract",
            "description": "双时态进入输出快照与幂等身份",
            "passed": {"as_of_effective_date", "as_known_at"}.issubset(snapshot_required)
            and "idempotency_key = SHA256(" in reliability
            and "+ as_of_effective_date" in reliability
            and "+ as_known_at" in reliability,
            "assertions": ["snapshot dual time", "idempotency dual time"],
        },
        {
            "id": "privacy_action_contract",
            "description": "隐私边界动作矩阵",
            "passed": all(
                token in privacy
                for token in (
                    "ALLOW",
                    "REDACT",
                    "BLOCK",
                    "Raw intake",
                    "Normalized facts",
                    "External service",
                    "S3-RESTRICTED",
                )
            ),
            "assertions": ["three actions", "five processing boundaries", "S0-S3 mapping"],
        },
        {
            "id": "test_target_contract",
            "description": "可量化测试门禁",
            "passed": all(
                token in release
                for token in ("25", "59/60/61", "179/180/181", "5个属性", "3个双时态", "8个端到端")
            ),
            "assertions": ["deterministic", "boundary", "property", "replay", "end-to-end"],
        },
    ]


def evaluate() -> list[dict[str, object]]:
    text = corpus()
    checks = [
        ("fact_rule_assumption", "事实、规则与假设分离", ["事实、规则与假设分离"]),
        ("month_decimal", "月度与Decimal确定性计算", ["Decimal", "按月计算"]),
        ("regional_isolation", "国家与地区规则隔离", ["地区规则可替换", "地区适配器"]),
        ("evidence_levels", "政策证据等级", ["政策证据模型", "等级"]),
        ("privacy_redaction", "隐私脱敏边界", ["隐私与安全", "脱敏"]),
        ("deterministic_kernel", "确定性内核与LLM边界", ["确定性内核", "非确定性"]),
        ("dependency_rules", "分层依赖规则", ["依赖规则", "domain/", "application/"]),
        ("bounded_contexts", "限界上下文", ["限界上下文", "Record Reconciliation"]),
        ("value_objects", "值对象与不变量", ["YearMonth", "Money", "不变量"]),
        ("scheme_jurisdiction", "险种制度与管辖角色", ["PensionScheme", "JurisdictionAssignment"]),
        ("policy_ruleset", "机器可执行政策规则集", ["PolicyRuleSet", "规则解析"]),
        ("bitemporal_policy", "政策双时态语义", ["PolicyValidTime", "SystemRecordedTime"]),
        ("immutable_run", "不可变分析运行快照", ["AnalysisRun", "不可变"]),
        ("ports_adapters", "入站与出站端口", ["入站端口", "出站端口"]),
        ("run_state_machine", "分析运行状态机", ["状态机", "RECEIVED", "RENDERED"]),
        ("error_taxonomy", "稳定错误码与恢复", ["MISSING_REQUIRED_FACT", "错误码"]),
        ("tool_envelope", "统一工具响应信封", ["schema_version", "run_id", "warnings"]),
        ("prompt_injection", "提示注入与不可信输入", ["提示注入", "不可信"]),
        ("privacy_lifecycle", "隐私威胁模型与保留期限", ["威胁模型", "保留期限"]),
        ("structured_output", "结构化单一事实源", ["analysis-output.schema.json", "单一事实源"]),
        ("probability_governance", "概率假设与独立性治理", ["独立性", "用户提供", "概率"]),
        ("idempotency_cache", "幂等、缓存与内容寻址", ["幂等", "缓存键", "内容寻址"]),
        ("observability_manifest", "可观测性与运行清单", ["可观测性", "运行清单"]),
        ("release_governance", "发布门禁与兼容性治理", ["发布门禁", "兼容性矩阵", "语义化版本"]),
    ]
    keyword_checks = [
        {
            "id": check_id,
            "description": description,
            "passed": all(token in text for token in tokens),
            "required_tokens": tokens,
        }
        for check_id, description, tokens in checks
    ]
    return keyword_checks + structural_checks()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--gaps", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = evaluate()
    passed = sum(1 for check in checks if check["passed"])
    score = round(passed / len(checks) * 100)
    gaps = len(checks) - passed
    if args.score:
        print(score)
    elif args.gaps:
        print(gaps)
    elif args.json:
        print(
            json.dumps(
                {"score": score, "gaps": gaps, "checks": checks}, ensure_ascii=False, indent=2
            )
        )
    else:
        print(f"Architecture coverage: {score}/100; remaining gaps: {gaps}")
        for check in checks:
            if not check["passed"]:
                print(f"GAP {check['id']}: {check['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
