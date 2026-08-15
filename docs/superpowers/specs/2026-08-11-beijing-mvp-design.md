# Beijing Pension Strategy MVP Design

## Goal

Build an installable `china-pension-strategy` Agent Skill that performs a reproducible Beijing pension contribution decision workflow using official national and Beijing policy sources. The MVP supports local informational screening, not production eligibility determination.

## Scope

The first vertical slice supports one scheme, enterprise employee basic pension insurance, and Beijing jurisdiction mappings. It provides:

- contribution-month reconciliation without overwriting competing totals;
- minimum contribution requirement and remaining-gap calculation;
- Beijing flexible-employment pension, medical, and unemployment contribution calculation where official rules support each item;
- employment-difficulty flexible-employment subsidy eligibility and duration assessment;
- monthly stop, continue, and subsidy-timing scenarios;
- conditional recommendation with limitations and invalidators;
- validated JSON and Markdown output.

The MVP accepts structured JSON. PDF/OCR ingestion, pension-benefit amount projection, medical/unemployment benefit calculation, remote services, databases, production signing, and DOCX/PDF rendering are out of scope. Immutable runs, manifests, privacy-safe audit events, and retention cleanup remain in scope because they are baseline execution contracts rather than optional production observability.

## Architecture

The implementation uses a full hexagonal package structure while remaining a single-process CLI:

```text
src/china_pension_strategy/
├── domain/
├── application/
├── ports/
│   ├── inbound/
│   └── outbound/
├── adapters/
│   ├── policies/
│   ├── regions/
│   ├── persistence/
│   └── reporting/
└── entrypoints/cli/
```

Domain objects are frozen dataclasses and import no framework, filesystem, HTTP, CLI, or adapter modules. Application use cases depend on domain objects and `Protocol` ports. Adapters implement policy files, Beijing jurisdiction mappings, local run storage, clocks, and JSON/Markdown rendering. The CLI constructs adapters and calls inbound use cases.

Runtime dependencies are `jsonschema`; test dependencies are `pytest` and `hypothesis`. Packaging uses `pyproject.toml` with a console command named `china-pension-strategy`.

## Skill Boundary

`SKILL.md` defines triggering, fact collection, privacy rules, CLI invocation, and structured-result explanation. It never calculates months, amounts, eligibility, or recommendation ranking. The authoritative result is produced by deterministic Python and validated against `analysis-output.schema.json`.

## Data Flow

```text
person-input.json
→ input schema and privacy validation
→ contribution reconciliation
→ bitemporal policy resolution
→ capability and eligibility assessment
→ deterministic monthly calculation
→ scenario comparison
→ recommendation
→ analysis-output.json
→ report.md
```

Input facts declare `required_for` capabilities. Missing precision facts can produce `PARTIAL`; a capability with no authoritative result is `BLOCKED`. A run is globally blocked only when no requested capability can produce a result or a safety/policy prerequisite fails. Each request freezes the normalized input, unresolved conflicts, selected rule digests, assumptions, objective, analysis horizon, dual-time values, engine/schema versions, and rounding profile in an immutable `AnalysisRun`.

Eligibility is mechanically derived from condition states:

- `ELIGIBLE`: every condition is `SATISFIED`;
- `INELIGIBLE`: at least one condition is `FAILED`;
- `UNKNOWN`: no condition failed and at least one is `UNVERIFIED`.

Recommendations may use `AVAILABLE` capabilities and explicitly bounded `PARTIAL` capabilities, never `BLOCKED` capabilities.

## Policy Acquisition And Rules

Official policy research uses read-only search and static-page retrieval. Accepted authorities are national government, ministry, Beijing municipal government, and authorized Beijing human-resources/social-security service sites. Every executable rule records:

- stable rule and source IDs;
- scheme, topic, jurisdiction role, and population scope;
- conditions, result, exceptions, and explicit overrides;
- effective and system-recorded time;
- source URL, issuing authority, document number when available, publication date, retrieval date, and stable text locator;
- content digest and rule test vectors.

Rules are stored in versioned JSON packages. `PolicyRepository` loads packages, the policy resolver selects applicable rules, and a deterministic evaluator executes `PolicyRule`, `DecisionTable`, and `ParameterTable`. `RegionPolicyProvider` supplies Beijing jurisdiction mappings only.

Before rules are implemented, the governing policy and release contracts will be versioned to define two executable environments:

- `PRODUCTION_APPROVED`: requires the existing domain review, dual approval, signing, and publication lifecycle;
- `MVP_REVIEWED`: requires official-source provenance, schema validation, rule tests, engineering review, and a local-only package status.

`MVP_REVIEWED` is executable only when `analysis_mode=LOCAL_MVP`. The application rejects it in production mode, the run cannot transition to `PUBLISHED`, artifacts remain `S1-INTERNAL` or `S2-CONFIDENTIAL`, and every output displays `NOT_PRODUCTION_APPROVED`. It cannot produce an official eligibility claim. Candidate and singly extracted rules remain non-executable. This is a formally enforced non-production lifecycle, not an implicit waiver of production dual approval.

If an official source does not support a condition or conflict resolution, the rule remains a candidate and cannot enter the executable package. The affected result becomes `UNKNOWN`, `BLOCKED`, or unsupported rather than receiving a guessed default.

## CLI

The CLI exposes:

```text
china-pension-strategy validate-policy POLICY_PACKAGE
china-pension-strategy analyze --input PERSON_JSON --as-of DATE --known-at TIMESTAMP --mode LOCAL_MVP
china-pension-strategy render --run-id RUN_ID --format markdown
china-pension-strategy cleanup --as-of TIMESTAMP
```

Every command writes one versioned tool envelope to stdout. `analyze` stores the raw schema-valid analysis result atomically behind `RunRepository`; envelope `data` returns `run_id`, status, and result/manifest references rather than embedding a second copy. `render` loads a validated result by `run_id`, stores the artifact, and returns its reference. Application use cases alone coordinate these operations; CLI and adapters never bypass the application layer.

| Exit | Envelope status | Meaning |
|---:|---|---|
| 0 | `success` | Command completed with all requested capabilities available |
| 2 | `partial` | Analysis completed with visible capability limitations |
| 10 | `error` | Input or policy validation failed |
| 20 | `error` | Analysis globally blocked |
| 30 | `error` | Calculation invariant failed |
| 40 | `error` | Rendering or storage failed |

## Structured Output Contract

Before calculation code, `analysis-output.schema.json` is versioned and extended with strict fields for:

- contribution/account fact summaries and recognized-month basis;
- contribution requirement, confirmed months, remaining gap, and competing gap results;
- policy evidence, rule IDs, package review status, source locators, dual-time applicability, and `NOT_PRODUCTION_APPROVED` notice;
- typed monthly pension, medical, and unemployment contribution amounts, subsidy, net outflow, and cumulative outflow;
- scenario horizon, actions, feasibility, outcome totals, thresholds, and sensitivity mode;
- recommendation objective, capability/assumption dependencies, limitations, thresholds, invalidators, and review triggers.

Input, policy package, tool envelope, run manifest, and analysis output each receive a versioned JSON Schema. Renderers consume only the stored validated analysis result.

## Run Storage And Reliability

The local file adapter stores content-addressed fact snapshots, rule packages, assumptions, results, manifests, and artifacts. `AnalysisRun` follows the contracted state machine through `VALIDATED` and `RENDERED`; `MVP_REVIEWED` runs cannot enter `PUBLISHED`. Results are written to a temporary sibling, schema/invariant checked, and atomically renamed. Idempotency includes case/input/rule/assumption/objective/horizon/double-time/version/rounding identity. Repeated identical requests return the same run ID.

Every validated run emits `run-manifest.json` with input, rule, assumption, objective, output and artifact digests plus component versions and validation status. Privacy-safe audit events are append-only and contain IDs, enums, counts, digests and durations only.

## Error Handling

The MVP implements at least:

- `INVALID_INPUT_SCHEMA`;
- `MISSING_REQUIRED_FACT`;
- `UNRESOLVED_RECORD_CONFLICT`;
- `AMBIGUOUS_POLICY_RULE`;
- `POLICY_VERSION_NOT_FOUND`;
- `RULESET_INCOMPATIBLE`;
- `PRIVACY_POLICY_VIOLATION`;
- `CALCULATION_INVARIANT_FAILED`;
- `ARTIFACT_RENDER_FAILED`.

Errors expose safe messages and recovery actions, never raw identity values, unrestricted file paths, or stack traces.

## Privacy

The input schema excludes raw identity-card, social-security, bank-card, verification-code, and query-serial fields. Each object carries classification, purpose, consent ID, creation time, expiry and deletion status. Boundary validation applies `ALLOW`, `REDACT`, or `BLOCK`. Local directories use least-privilege permissions; sensitive temporary files are deleted on success and failure. `cleanup` expires inputs, normalized facts, runs, reports and audit identifiers according to the documented retention schedule and emits a non-sensitive deletion manifest.

Tests and fixtures use synthetic data only. No user input or policy document is uploaded to a third party. Privacy tests cover names, phone numbers, addresses, free text, amounts, paths, identity/social-security/bank identifiers, verification codes, and query serials across output, errors, logs and temporary files.

## Scenarios And Assumptions

Each scenario declares an inclusive monthly horizon, action sequence, objective, and assumption references. Monthly cash flow keeps pension, medical, and unemployment contributions separate, then records subsidy, net and cumulative outflow. The MVP supports minimum-compliance-cost, near-term-cash-flow and subsidy-timing objectives.

Probability is optional. Qualifying official statistics use evidence-backed mode; user/expert values remain labeled assumptions. Without qualifying evidence, scenarios use threshold, range, or conservative/base/optimistic modes. Recommendations expose thresholds, assumption provenance, limitations and invalidators.

## Testing And Acceptance

Tests follow red-green-refactor and include:

- at least 25 deterministic examples;
- explicit 59/60/61-month and 179/180/181-month boundaries;
- at least 5 Hypothesis properties;
- at least 3 bitemporal replay cases;
- at least 8 CLI end-to-end evals;
- policy source, effective-period, locator, digest, review-status, and test-vector checks;
- architecture import tests that reject inward-layer dependencies on adapters;
- deterministic output digest checks;
- complete `AnalysisRun` state-transition and idempotency checks;
- atomic publication and `run-manifest.json` digest-integrity checks;
- Decimal, per-insurance/per-month rounding, decision-table completeness, and cross-platform normalized-result checks;
- JSON Schema validation for input, policy package, tool envelope, and analysis output;
- privacy lifecycle, consent, permissions, expiry/deletion, temporary cleanup, and prohibited-value checks.

At least one E2E fixture covers each MVP capability, and eight fixtures cover success, partial, global blocking, record conflict, unknown eligibility, policy ambiguity/version miss, deterministic replay, and render/cleanup behavior. A complete synthetic person example must run from CLI input through stored JSON, manifest, and Markdown output using only executable `MVP_REVIEWED` rules.

Acceptance commands and pass criteria:

```text
python -m pytest -q                         # zero failures; required case counts collected
python -m pytest tests/architecture -q      # zero forbidden dependency imports
python -m pytest tests/e2e -q               # at least 8 passing E2E fixtures
python test_design_contracts.py             # all design contract tests pass
python verify_design_docs.py                # PASS, no broken links/schema/sensitive findings
python audit_architecture.py --gaps          # prints 0
```

Two repeated runs with identical frozen identity must return the same run ID and normalized output digest. Supported Windows and Linux CI jobs must produce the same normalized digest for golden fixtures.
