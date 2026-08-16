# Contributing to China Pension Strategy

Contributions are welcome when they preserve the project's evidence,
determinism, privacy, and replay guarantees. Read
`.specify/memory/constitution.md` before proposing a change.

## Development setup

Python 3.12 or newer is required.

```text
python -m venv .venv
python -m pip install -e ".[test,quality]"
python -m pytest -q
python -m ruff format --check .
python -m ruff check .
python -m mypy src/china_pension_strategy
```

Use synthetic records in tests, examples, issue descriptions, and pull
requests. Never commit pension statements, identity numbers, contact details,
financial account data, run artifacts, or audit logs derived from a real
person.

Windows contributors who encounter pytest temporary-directory permission
errors should read `docs/sandbox-capabilities.md`; the compatibility bootstrap
is test-only and is a no-op on Linux and macOS.

## Policy evidence requirements

Every executable policy value MUST be supported by a verifiable authoritative
source accepted by the policy schema. In the current schema, provenance URLs
must use HTTPS on a `gov.cn` host. A plausible rate, media report, search result,
telephone answer, or model-generated interpretation is not sufficient evidence
for an executable rule.

Each policy contribution MUST include:

- the authoritative source URL, issuing authority, document number when
  available, publication date, retrieval time, stable locator, and exact quoted
  passage;
- an engineering explanation that distinguishes the source text from the
  interpretation encoded by the rule;
- explicit effective-time and transaction-time boundaries;
- deterministic rule vectors covering ordinary and boundary cases;
- the affected jurisdiction role and pension scheme.

Mirrors may help cross-check availability, but package provenance must retain
the authoritative URL required by the schema. Unsupported conditions must
remain `UNKNOWN`, `PARTIAL`, or `BLOCKED`; do not insert a default value.

## Evidence digest chain

Changing evidence requires updating the complete digest chain in order:

1. Edit the `## 来源：<source_id>` section in `references/`.
2. Recompute the section's canonical SHA-256 using the same normalization as
   `canonical_source_digest()` in `tests/policy/test_official_packages.py`.
3. Update the matching `policy-data/sources/*.json` `source_digest`.
4. Update the matching entry in `policy-data/source-digests.json`.
5. Update package provenance and recompute the package `content_digest`.

Do not hand-wave or partially update this chain. The policy contract tests
recompute the values and must fail when any link is stale.

## Bitemporal and version rules

- A package's `transaction_from` MUST NOT precede any referenced source's
  `retrieved_at`, engineering review time, or production approval time.
- New evidence creates a new known-at version. Do not backdate
  `transaction_from` to make an existing fixture pass.
- When transaction time changes, update the affected `AS_KNOWN_AT` test values
  and fixture creation times explicitly.
- Keep replaced packages replayable. A deliberately archived past-period
  package MUST set `historical: true` so it cannot pollute the current expiry
  gate.
- Never edit a published run in place. Changed facts, policies, assumptions, or
  engine behavior create a new run.

## Determinism and skill boundaries

Existing fixture `run_id` values are regression contracts. In particular, the
Beijing guard case must remain:

```text
run-95e2c71f61a9b8510cc4097e9c930d53afb36a4892be154802ac96c4687731e9
```

If an intended semantic change alters a run ID, document the changed canonical
inputs and obtain review before updating the fixture. Formatting-only,
documentation-only, or performance changes must not change normalized result
digests.

`SKILL.md` MUST NOT inline policy percentages, subsidy ratios, contribution
bases, or benefit amounts. Store policy values in approved rule packages and
render only validated structured results.

## Architecture rules

- Domain code does not import file systems, HTTP clients, databases, LLM SDKs,
  document renderers, or framework types.
- Application code depends on domain types and ports, not concrete adapters.
- Entry points parse requests and map responses; they do not contain policy or
  calculation logic.
- Reports and charts consume frozen structured results and never recalculate
  authoritative values.

Run `python audit_architecture.py --gaps` after changing package boundaries or
imports.

## Required checks

Run these commands before opening a pull request:

```text
python -m pytest -q
python -m ruff format --check .
python -m ruff check .
python -m mypy src/china_pension_strategy
python verify_design_docs.py
python test_design_contracts.py
python audit_architecture.py --gaps
python scripts/policy_expiry_report.py --horizon-months 6
```

The expiry report is an advisory for maintainers until the affected current
policy package can be updated. All other commands must exit successfully.

## Pull request checklist

- State the user-visible behavior and the smallest supported scope.
- List affected schemas, rules, jurisdictions, privacy boundaries, and replay
  baselines.
- For policy changes, attach the source URL, document number, publication date,
  retrieval date, quoted passage, and rule mapping.
- Explain every expected golden digest or `run_id` change.
- Confirm tests use synthetic data and no `runs/`, JSONL logs, caches, or local
  paths are included.
- Confirm the applicable MIT or CC0 license boundary described in `NOTICE`.
