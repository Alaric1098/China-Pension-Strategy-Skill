# Beijing Pension Strategy MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an installable, deterministic Beijing pension-strategy Skill covering contribution reconciliation, minimum-year gaps, flexible-employment contributions, subsidy eligibility/timing, scenarios, and conditional recommendations.

**Architecture:** Implement a single-process CLI with full hexagonal boundaries. Frozen dataclass domain objects and pure services sit inside application use cases and Protocol ports; versioned file, Beijing-region, persistence, reporting, and CLI adapters sit outside. Real official rules execute only in `LOCAL_MVP` with enforced `MVP_REVIEWED` notices.

**Tech Stack:** Python 3.12+, dataclasses, Decimal, jsonschema, pytest, Hypothesis, JSON Schema 2020-12

---

### Task 1: Package And Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/china_pension_strategy/__init__.py`
- Create: package `__init__.py` files under `domain/`, `application/`, `ports/inbound/`, `ports/outbound/`, `adapters/`, and `entrypoints/cli/`
- Create: `tests/architecture/test_dependencies.py`

1. Write an architecture test that discovers and parses every source module and fails if `domain` imports application, ports, adapters, entrypoints, Pydantic, filesystem, HTTP, or CLI modules.
2. Run `python -m pytest tests/architecture/test_dependencies.py -q`; expect failure because the package does not exist.
3. Add the minimal package and `pyproject.toml` with runtime `jsonschema` and test extras `pytest`, `hypothesis`.
4. Install editable test dependencies with `python -m pip install -e ".[test]"`.
5. Re-run the architecture test; expect pass.

### Task 2: Governance And JSON Contracts

**Files:**
- Modify: `docs/policy-model.md`
- Modify: `docs/release-governance.md`
- Modify: `docs/schemas/analysis-output.schema.json`
- Create: `schemas/person-input.schema.json`
- Create: `schemas/policy-package.schema.json`
- Create: `schemas/tool-envelope.schema.json`
- Create: `schemas/run-manifest.schema.json`
- Create: `tests/contracts/test_schemas.py`

1. Write failing schema tests for `LOCAL_MVP`, `MVP_REVIEWED`, contribution gaps, policy evidence, typed monthly cash flows, scenario outcomes, recommendation limits, and manifest digests.
2. Run `python -m pytest tests/contracts/test_schemas.py -q`; expect failures for missing schemas/fields.
3. Version the governing contracts and implement strict schemas with `additionalProperties: false`.
4. Validate representative valid and invalid instances with `jsonschema`.
5. Re-run the schema tests; expect pass.

### Task 3: Domain Values And Eligibility

**Files:**
- Create: `src/china_pension_strategy/domain/values.py`
- Create: `src/china_pension_strategy/domain/facts.py`
- Create: `src/china_pension_strategy/domain/eligibility.py`
- Create: `src/china_pension_strategy/domain/errors.py`
- Create: `tests/domain/test_values.py`
- Create: `tests/domain/test_eligibility.py`

1. Write failing tests for closed `YearMonth`, inclusive month counts, `Money`/Decimal rounding, immutable fact references, capability states, and eligibility derivation.
2. Run the domain tests; expect import failures.
3. Implement the smallest frozen dataclasses and enums that satisfy the tests.
4. Add Hypothesis properties for month-count monotonicity and eligibility state derivation.
5. Re-run the domain tests; expect pass.

### Task 4: Policy Domain And Resolver

**Files:**
- Create: `src/china_pension_strategy/domain/policy.py`
- Create: `src/china_pension_strategy/application/resolve_policy.py`
- Create: `src/china_pension_strategy/ports/outbound/policy_repository.py`
- Create: `tests/domain/test_policy.py`
- Create: `tests/application/test_policy_resolver.py`

1. Write failing tests for dual-time matching, legal hierarchy, explicit override, ambiguity, engine compatibility, package review status, and rejection of `MVP_REVIEWED` outside `LOCAL_MVP`.
2. Run the tests; expect failures.
3. Implement immutable policy objects, repository Protocol, and deterministic resolver.
4. Add three historical replay tests and decision-table overlap/gap checks.
5. Re-run; expect pass.

### Task 5: Official Policy Research And Rule Packages

**Files:**
- Create: `policy-data/sources/*.json`
- Create: `policy-data/packages/national-enterprise-pension.json`
- Create: `policy-data/packages/beijing-flex-employment.json`
- Create: `policy-data/packages/beijing-flex-subsidy.json`
- Create: `references/national-rules.md`
- Create: `references/regions/beijing.md`
- Create: `tests/policy/test_official_packages.py`

1. Use agent-reach search/static retrieval to collect national and Beijing official sources current at `2026-08-11`.
2. Record URLs, authority, dates, locators, retrieved time, source digest, and exact supported interpretation; do not store unsupported inferred rules.
3. Write failing package tests for provenance, effective periods, review status, content digests, and rule vectors.
4. Encode only source-supported `MVP_REVIEWED` rules and parameters.
5. Run `python -m pytest tests/policy/test_official_packages.py -q`; expect pass.

### Task 6: Contribution Reconciliation

**Files:**
- Create: `src/china_pension_strategy/domain/reconciliation.py`
- Create: `src/china_pension_strategy/application/reconcile_records.py`
- Create: `tests/domain/test_reconciliation.py`

1. Write failing tests for duplicate months, competing aggregate/detail totals, separate schemes, and unresolved conflict preservation.
2. Include 179/180/181 and the 200-month versus 17-year-1-month case.
3. Implement pure reconciliation and application orchestration.
4. Add a property that adding one unique valid contribution month cannot reduce confirmed months.
5. Run tests; expect pass.

### Task 7: Gap, Contribution, And Subsidy Engines

**Files:**
- Create: `src/china_pension_strategy/domain/calculation.py`
- Create: `src/china_pension_strategy/application/calculate_months.py`
- Create: `tests/domain/test_calculation.py`

1. Write failing tests for minimum-month schedules, remaining gaps, pension/medical/unemployment contributions, policy-directed rounding, subsidy amounts, start/end months, and unknown eligibility.
2. Include 59/60/61-month subsidy boundaries and annual parameter transitions.
3. Implement a deterministic evaluator over resolved rule/parameter/decision tables; do not branch on Beijing literals in the core.
4. Add properties: one added paid month cannot increase the gap; a higher subsidy cannot increase net outflow; identical input yields identical canonical values.
5. Run tests; expect pass.

### Task 8: Scenario And Recommendation Engines

**Files:**
- Create: `src/china_pension_strategy/domain/scenario.py`
- Create: `src/china_pension_strategy/application/analyze_scenarios.py`
- Create: `src/china_pension_strategy/application/recommend.py`
- Create: `tests/domain/test_scenarios.py`

1. Write failing tests for stop/continue/subsidy-timing action sequences, inclusive horizon, separate insurance cash flows, threshold/range/scenario assumptions, objectives, limitations, invalidators, and blocked-capability exclusion.
2. Implement monthly scenario generation and deterministic ranking.
3. Add properties for cumulative cash-flow sums and deterministic ranking.
4. Run tests; expect pass.

### Task 9: Immutable Runs, Ports, And Local Storage

**Files:**
- Create: `src/china_pension_strategy/domain/run.py`
- Create: `src/china_pension_strategy/application/analyze.py`
- Create: `src/china_pension_strategy/ports/outbound/run_repository.py`
- Create: `src/china_pension_strategy/ports/outbound/clock.py`
- Create: `src/china_pension_strategy/adapters/persistence/file_run_repository.py`
- Create: `tests/application/test_analysis_run.py`
- Create: `tests/adapters/test_file_run_repository.py`

1. Write failing tests for legal state transitions, frozen run identity, idempotent run IDs, atomic result publication, manifest integrity, and `MVP_REVIEWED` prohibition on `PUBLISHED`.
2. Implement Protocol ports, use case, content addressing, temporary sibling writes, and atomic rename.
3. Test interrupted writes and digest mismatches.
4. Run tests; expect pass.

### Task 10: Input, Privacy, Retention, And Audit Adapters

**Files:**
- Create: `src/china_pension_strategy/adapters/input/json_input.py`
- Create: `src/china_pension_strategy/adapters/privacy/scanner.py`
- Create: `src/china_pension_strategy/adapters/persistence/retention.py`
- Create: `src/china_pension_strategy/adapters/audit/jsonl_audit.py`
- Create: `tests/adapters/test_privacy.py`
- Create: `tests/adapters/test_retention.py`

1. Write failing tests for schema validation, consent/classification metadata, prohibited fields/values, safe errors/logs, restrictive permissions, expiry, deletion manifests, and temporary cleanup on success/failure.
2. Implement deterministic `ALLOW/REDACT/BLOCK` scanning and local lifecycle adapters.
3. Cover names, phones, addresses, free text, amounts, paths, identity/social-security/bank identifiers, verification codes, and query serials.
4. Run tests; expect pass.

### Task 11: Policy, Region, Reporting, And CLI Adapters

**Files:**
- Create: `src/china_pension_strategy/adapters/policies/json_policy_repository.py`
- Create: `src/china_pension_strategy/adapters/regions/beijing.py`
- Create: `src/china_pension_strategy/adapters/reporting/json_renderer.py`
- Create: `src/china_pension_strategy/adapters/reporting/markdown_renderer.py`
- Create: `src/china_pension_strategy/entrypoints/cli/main.py`
- Create: `tests/adapters/test_policy_repository.py`
- Create: `tests/adapters/test_reporting.py`
- Create: `tests/e2e/test_cli.py`

1. Write failing adapter and CLI tests for policy validation, analyze, render-by-run-ID, cleanup, envelopes, stable exit codes, partial/global blocking, and safe failures.
2. Implement adapters and composition root without business logic in the CLI.
3. Add at least eight E2E fixtures covering every MVP capability and required failure mode.
4. Run adapter and E2E tests; expect pass.

### Task 12: Agent Skill And Golden Evaluation

**Files:**
- Create: `SKILL.md`
- Create: `evals/evals.json`
- Create: `evals/fixtures/*.json`
- Create: `tests/e2e/test_skill_contract.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

1. Write a failing Skill contract test for frontmatter, trigger coverage, privacy workflow, CLI commands, no inline calculations, output handling, `LOCAL_MVP`, and disclaimer behavior.
2. Create concise `SKILL.md` and synthetic eval fixtures.
3. Execute a golden case through analyze, stored JSON/manifest, and Markdown rendering.
4. Update project status and supported/unsupported capability documentation.
5. Run the complete verification suite:

```text
python -m pytest -q
python -m pytest tests/architecture -q
python -m pytest tests/e2e -q
python test_design_contracts.py
python verify_design_docs.py
python audit_architecture.py --gaps
```

Expected: zero test failures, document verification `PASS`, architecture gaps `0`, at least 25 deterministic cases, 5 properties, 3 replay cases, and 8 E2E cases.

The workspace is not a Git repository, so commit steps are omitted. If Git is initialized later, commit after each green task without amending prior commits.
