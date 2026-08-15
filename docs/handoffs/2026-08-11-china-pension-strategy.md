# China Pension Strategy Handoff

## Objective

Continue implementing the real-policy Beijing MVP Agent Skill in `C:\Projects\Workspace\china-pension-strategy` using the approved full hexagonal architecture and TDD.

## Authoritative Artifacts

- MVP design: `docs/superpowers/specs/2026-08-11-beijing-mvp-design.md`
- Implementation plan: `docs/plans/2026-08-11-beijing-mvp.md`
- Contract-closure design: `docs/superpowers/specs/2026-08-11-contract-closure-design.md`
- Existing project contracts: `README.md` and `docs/*.md`

Do not redesign these unless a verified contradiction requires a versioned contract change.

## Completed Checkpoints

- Task 1 package/test harness: complete, specification and quality approved.
- Task 2 governance and JSON contracts: complete after multiple adversarial fixes, specification and quality approved.
- Task 3 domain values/facts/eligibility: complete, specification and quality approved.
- Task 4 policy domain/resolver: specification approved; quality review is open and blocks progress.
- Latest complete test run before the open review: 159 tests passed.
- Workspace is not a Git repository. Do not attempt worktrees or commits.

## Current Open Work

Resume Task 4 with the existing implementer context if available, otherwise inspect:

- `src/china_pension_strategy/domain/policy.py`
- `src/china_pension_strategy/application/resolve_policy.py`
- `src/china_pension_strategy/ports/outbound/policy_repository.py`
- `schemas/policy-package.schema.json`
- `tests/domain/test_policy.py`
- `tests/application/test_policy_resolver.py`

The Task 4 quality reviewer reported five unresolved issues:

1. Bitemporal causality: package `transaction_from` must not precede provenance retrieval, engineering review, or production publication/approval timestamps. Existing fixtures may need corrected chronology.
2. Executable type safety: validate inputs, conditions, typed literals, operators, expression arity, reference types, parameter types, exception effects, and test-vector types. Schema-valid references must match declared input/parameter/output types.
3. Decision-table resource bound: reject tables whose Cartesian domain exceeds a fixed documented maximum before enumeration; add schema cardinality limits and boundary tests.
4. Qualified rule identity: package-local bare rule IDs currently collide across packages. Resolver identity and ambiguity output must use qualified IDs. Overrides must be scoped safely and support explicit cross-package qualification without deleting unrelated same-ID rules.
5. Semantic canonicalization: Python `True == 1` can collapse different parameter signatures. Canonical signatures must include scalar type tags and validated expression/reference types.

Apply fixes with strict red-green-refactor. Re-dispatch the Task 4 quality reviewer after fixes. Do not proceed to Task 5 until both Task 4 specification and quality reviews are APPROVED.

## Remaining Plan

After Task 4 approval, continue sequentially from Task 5 in `docs/plans/2026-08-11-beijing-mvp.md`:

- Task 5 official policy research and real `MVP_REVIEWED` rule packages
- Task 6 contribution reconciliation
- Task 7 gap/contribution/subsidy engines
- Task 8 scenarios and recommendations
- Task 9 immutable runs and storage
- Task 10 privacy/retention/audit adapters
- Task 11 policy/region/reporting/CLI adapters
- Task 12 `SKILL.md`, evals, golden E2E verification

For Task 5, explicitly announce use of agent-reach web search/static retrieval. Accept only official `gov.cn` hosts and preserve source URL, authority level, locator, effective date, retrieval time, digest, and test vectors. Rules remain `MVP_REVIEWED`, local-only, and must display `NOT_PRODUCTION_APPROVED`.

## Verification Commands

Run after each task and before any completion claim:

```text
python -m pytest -q
python test_design_contracts.py
python verify_design_docs.py
python audit_architecture.py --gaps
```

Final acceptance also requires architecture and E2E focused suites from the implementation plan.

## Suggested Skills

- `using-superpowers`
- `subagent-driven-development`
- `test-driven-development`
- `systematic-debugging` when a regression appears
- `agent-reach` for Task 5 official policy research
- `verification-before-completion`
- `requesting-code-review`

## Working Rules

- Use `apply_patch` for manual file edits.
- Do not modify unrelated user changes.
- Keep domain/application free of adapter and external-driver imports.
- Never invent policy values, probabilities, eligibility facts, or source approval.
- Fresh implementer per task; specification review before quality review; fix and re-review every finding.
