import json
import unittest
from pathlib import Path

import audit_architecture

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "docs" / "schemas" / "analysis-output.schema.json"


class OutputSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_output_requires_core_contract_collections(self):
        required = set(self.schema["required"])
        self.assertTrue(
            {
                "capabilities",
                "eligibility_assessments",
                "record_conflicts",
                "policy_ambiguities",
                "assumptions",
            }.issubset(required)
        )

    def test_snapshot_requires_dual_time(self):
        required = set(self.schema["properties"]["snapshot"]["required"])
        self.assertIn("as_of_effective_date", required)
        self.assertIn("as_known_at", required)

    def test_eligibility_and_capability_enums_are_closed(self):
        definitions = self.schema["$defs"]
        self.assertEqual(
            definitions["eligibilityAssessment"]["properties"]["status"]["enum"],
            ["ELIGIBLE", "INELIGIBLE", "UNKNOWN"],
        )
        self.assertEqual(
            definitions["capabilityAssessment"]["properties"]["status"]["enum"],
            ["AVAILABLE", "PARTIAL", "BLOCKED"],
        )

    def test_probability_modeling_modes_are_explicit(self):
        assumption = self.schema["$defs"]["assumption"]
        modes = assumption["properties"]["modeling_mode"]["enum"]
        self.assertEqual(
            modes,
            [
                "EVIDENCE_BACKED_PROBABILITY",
                "USER_ASSUMPTION",
                "EXPERT_ASSUMPTION",
                "SCENARIO_ONLY",
                "THRESHOLD",
                "RANGE",
            ],
        )
        self.assertIn("event_definition", assumption["required"])
        self.assertIn("distribution", assumption["properties"])
        self.assertTrue(
            {"source_date", "population", "approved_by", "expires_at"}.issubset(
                assumption["required"]
            )
        )
        self.assertIn("oneOf", assumption)
        self.assertEqual(assumption["properties"]["provenance_refs"]["minItems"], 1)
        serialized = json.dumps(assumption, ensure_ascii=False)
        self.assertIn('"const": "EVIDENCE_BACKED_PROBABILITY"', serialized)
        self.assertIn('"const": "official_statistic"', serialized)
        for field in ("source_date", "population", "provenance_refs", "approved_by", "expires_at"):
            self.assertIn(field, serialized)

    def test_eligibility_status_is_derived_from_conditions(self):
        assessment = self.schema["$defs"]["eligibilityAssessment"]
        self.assertIn("allOf", assessment)
        serialized = json.dumps(assessment, ensure_ascii=False)
        for status in ("ELIGIBLE", "INELIGIBLE", "UNKNOWN", "SATISFIED", "FAILED", "UNVERIFIED"):
            self.assertIn(f'"const": "{status}"', serialized)
        self.assertIn('"not"', serialized)

    def test_partial_status_requires_warning(self):
        serialized = json.dumps(self.schema, ensure_ascii=False)
        self.assertIn('"const": "partial"', serialized)
        self.assertIn('"minItems": 1', serialized)


class DocumentationContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_readme_uses_capability_requirements_and_rule_evaluator(self):
        readme = self.read("README.md")
        self.assertIn("required_for", readme)
        self.assertIn("ELIGIBLE", readme)
        self.assertIn("PolicyRule", readme)
        self.assertNotIn("补贴上限 = min(实际缴费额, 当年最低缴费额) × 补贴比例", readme)

    def test_idempotency_includes_dual_time(self):
        reliability = self.read("docs/computation-and-reliability.md")
        key_block = reliability.split("idempotency_key = SHA256(", 1)[1].split(")", 1)[0]
        self.assertIn("as_of_effective_date", key_block)
        self.assertIn("as_known_at", key_block)

    def test_privacy_contract_defines_boundary_actions(self):
        privacy = self.read("docs/security-and-privacy.md")
        self.assertIn("ALLOW", privacy)
        self.assertIn("REDACT", privacy)
        self.assertIn("BLOCK", privacy)
        self.assertIn("External service", privacy)

    def test_test_targets_are_measurable(self):
        release = self.read("docs/release-governance.md")
        for target in ("25", "59/60/61", "179/180/181", "5个属性", "3个双时态", "8个端到端"):
            self.assertIn(target, release)


class ArchitectureAuditTests(unittest.TestCase):
    def test_audit_contains_structural_contract_checks(self):
        checks = {check["id"]: check for check in audit_architecture.evaluate()}
        for check_id in (
            "output_schema_contract",
            "eligibility_capability_contract",
            "probability_evidence_contract",
            "dual_time_identity_contract",
            "privacy_action_contract",
            "test_target_contract",
        ):
            self.assertIn(check_id, checks)
            self.assertTrue(checks[check_id]["passed"], check_id)


if __name__ == "__main__":
    unittest.main()
