# Design Contract Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the README, design documents, output schema, and automated audits express one enforceable pension-analysis contract.

**Architecture:** Treat the JSON output schema as the machine contract and align prose around it. Keep policy selection in the resolver/repository, deterministic rule execution in the core, and jurisdiction mapping in the region provider.

**Tech Stack:** Markdown, JSON Schema 2020-12, Python standard library `unittest`

---

### Task 1: Add Contract Tests

**Files:**
- Create: `test_design_contracts.py`

1. Add failing tests for eligibility enums, capability states, dual-time snapshot fields, conflict collections, probability modeling modes, privacy actions, and numeric test targets.
2. Run `python -m unittest -v test_design_contracts.py` and confirm failures against the current contract.

### Task 2: Close The Output Schema

**Files:**
- Modify: `docs/schemas/analysis-output.schema.json`

1. Add strict definitions for eligibility conditions and assessments, capabilities, conflicts, ambiguities, assumptions, scenarios, recommendations, warnings, and errors.
2. Require effective and known-at times in the snapshot.
3. Encode status invariants for `success` and `partial`.
4. Run the contract tests and confirm schema-focused tests pass.

### Task 3: Align Design Documents

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/domain-model.md`
- Modify: `docs/policy-model.md`
- Modify: `docs/runtime-contracts.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/computation-and-reliability.md`
- Modify: `docs/security-and-privacy.md`
- Modify: `docs/release-governance.md`

1. Define capability-specific input requirements and three-valued eligibility.
2. Replace the generic subsidy formula with deterministic execution of approved policy rules.
3. Clarify resolver precedence, global versus capability blocking, probability fallback, dual-time idempotency, and privacy boundary actions.
4. Set measurable deterministic, property, replay, and end-to-end test targets.
5. Run contract tests and confirm documentation assertions pass.

### Task 4: Upgrade Auditing And Verify

**Files:**
- Modify: `audit_architecture.py`
- Modify: `verify_design_docs.py`
- Modify: `CHANGELOG.md`

1. Add structural contract checks instead of relying only on keyword presence.
2. Include the new tests in the documented verification path.
3. Run `python -m unittest -v test_design_contracts.py`, `python verify_design_docs.py`, and `python audit_architecture.py --json`.
4. Confirm all commands pass without warnings or sensitive-data findings.

The workspace is not a Git repository, so commit steps are intentionally omitted.
