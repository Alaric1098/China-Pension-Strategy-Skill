<!--
Sync Impact Report
- Version change: unratified template -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. Evidence Before Conclusions
  - Template Principle 2 -> II. Deterministic and Traceable Computation
  - Template Principle 3 -> III. Policy, Time, and Jurisdiction Isolation
  - Template Principle 4 -> IV. Privacy and Security by Default
  - Template Principle 5 -> V. Contract-Driven Quality Gates
- Added sections:
  - Architecture and Domain Constraints
  - Development Workflow and Quality Gates
- Removed sections: None
- Follow-up TODOs: None
-->
# China Pension Strategy Constitution

## Core Principles

### I. Evidence Before Conclusions

The system MUST keep personal facts, official rules, administrative guidance,
calculation assumptions, and unresolved questions as distinct data with source,
date, and confidence or approval state. Reported aggregates MUST NOT overwrite
derived detail, and conflicting claims MUST remain visible until resolved with
recorded evidence. Only competent authorities may produce an official
determination; system output MUST remain an assessment. Missing evidence MUST
produce `UNKNOWN`, `PARTIAL`, or `BLOCKED` outcomes rather than guessed facts,
eligibility, or probabilities. This separation prevents plausible language from
being mistaken for an authoritative pension decision.

### II. Deterministic and Traceable Computation

Every authoritative month, amount, eligibility state, cash-flow result, and
recommendation ranking MUST be produced by deterministic code from validated,
approved inputs. Monetary calculations MUST use `Decimal`; periods MUST use
explicit closed `YearMonth` boundaries; and each insurance type MUST preserve
its policy-defined rounding stage. Identical normalized facts, policy snapshots,
assumptions, objectives, engine and schema versions, and rounding profiles MUST
produce identical structured results and content digests. Every published value
and recommendation MUST trace to its facts, executable rules, assumptions, and
run manifest. LLMs MAY discover or explain candidates but MUST NOT alter frozen
facts, execute natural-language policy, invent probabilities, or recompute
authoritative results.

### III. Policy, Time, and Jurisdiction Isolation

Executable policy MUST reside in approved, versioned rule packages with stable
rule identifiers, authoritative source excerpts, evidence level, effective time,
transaction time, jurisdiction role, approval state, and compatibility range.
Rule resolution MUST consider pension scheme, jurisdiction role,
`as_of_effective_date`, and `as_known_at`; ambiguity or incompatibility MUST fail
explicitly and MUST NOT trigger silent fallback. National rules, regional rules,
and personal facts MUST remain separate. Months, schemes, or regions MUST NOT be
combined without an explicit transfer, conversion, or coordination rule.
Superseded packages and historical runs MUST remain replayable so corrections do
not rewrite prior knowledge.

### IV. Privacy and Security by Default

All user files, OCR text, web content, metadata, and tool output MUST be treated
as untrusted data. Processing MUST be local-first, purpose-limited,
data-minimized, and bounded by explicit authorization and retention periods.
Repositories, commits, fixtures, and general logs MUST contain only public or
approved internal data; tests MUST use synthetic identities and records.
Restricted identifiers and raw pension records MUST NOT enter prompts, logs,
reports, or external services. Each data-boundary decision MUST resolve to
`ALLOW`, `REDACT`, or `BLOCK`; absent authorization, unverifiable service policy,
or failed minimization MUST resolve to `BLOCK`. Prompt injection, identity
mix-up, source poisoning, digest mismatch, and retention deletion MUST have
deterministic controls and auditable failure responses.

### V. Contract-Driven Quality Gates

Behavior MUST be defined through versioned schemas, ports, executable rules,
domain invariants, and acceptance tests before it is treated as supported.
Changes to calculation, policy resolution, privacy boundaries, or public
contracts MUST add or update failing tests before implementation and then pass
the complete affected test set. Releases MUST pass unit, property, integration,
contract, architecture, end-to-end, historical replay, privacy, and sensitive
data checks appropriate to the change. Golden-result digest changes MUST be
explained and approved. A failing gate, unsupported region, ambiguous rule, or
incompatible version MUST stop publication; manual review of a sample report is
not a substitute for automated verification.

## Architecture and Domain Constraints

- The system MUST preserve the controlled intelligent shell and deterministic
  kernel boundary. Candidate extraction and narrative generation stay outside
  authoritative calculation.
- Dependencies MUST point inward: entry points call application use cases;
  application code depends on domain types and ports; adapters implement ports.
  Domain code MUST NOT depend on file systems, HTTP, databases, LLM SDKs,
  document renderers, or framework-specific types.
- Bounded contexts MUST exchange immutable values through identifiers and ports,
  not shared mutable domain objects. Published scenarios and results are
  immutable; changed facts, policy, or assumptions create a new version.
- Eligibility MUST be mechanically derived as `ELIGIBLE`, `INELIGIBLE`, or
  `UNKNOWN`. Capability MUST be mechanically derived as `AVAILABLE`, `PARTIAL`,
  or `BLOCKED`. Narrative and rendering layers MUST NOT override these states or
  hide conflicts, uncertainty, or blocked dependencies.
- Reports and charts MUST consume the validated structured result only. They
  MUST NOT parse policy, rerun calculations, or maintain independent values.
- Complexity MUST serve reproducibility or a measured operational need. The
  default architecture is a single process with explicit ports and local
  storage; remote services, workflow engines, or multi-agent topology require
  evidence from performance, concurrency, recovery, or compliance tests.

## Development Workflow and Quality Gates

1. Each change MUST start with a specification that identifies supported users,
   jurisdiction and scheme boundaries, facts, rules, assumptions, error states,
   privacy classification, and measurable acceptance criteria.
2. Planning MUST include a Constitution Check covering all five principles,
   affected contracts, policy versions, data boundaries, replay impact, and the
   smallest design that satisfies the specification.
3. Tasks MUST preserve dependency direction and MUST include tests for boundary
   months, rounding, conflicts, unknown states, unsupported jurisdictions,
   double-time policy selection, privacy enforcement, and deterministic replay
   whenever those concerns are affected.
4. Implementation MUST NOT silently broaden product scope, evidence claims,
   supported regions, or production approval status. Unsupported behavior MUST
   remain explicit.
5. Before completion, contributors MUST run the relevant automated suite. A
   full release candidate MUST pass `python -m pytest -q`, architecture and E2E
   suites, design-contract validation, documentation validation, and the
   architecture gap audit with zero unexplained failures or gaps.
6. Production publication additionally MUST satisfy the signed component,
   policy approval, compatibility, security, migration, rollback, and release
   evidence requirements in `docs/release-governance.md`. `MVP_REVIEWED` policy
   packages MUST remain local-only and MUST NOT be represented as production or
   official eligibility determinations.

## Governance

This constitution is the highest project-level engineering governance document.
Specifications, plans, tasks, implementation, reviews, and releases MUST comply
with it. `README.md` and the documents under `docs/` provide operational detail;
when they conflict with this constitution, the constitution controls and the
dependent document MUST be reconciled before the affected change proceeds.

Amendments MUST be proposed as an explicit constitution change with rationale,
affected principles or sections, migration impact, and a Sync Impact Report.
Approval requires review by a project maintainer and, when policy, privacy, or
production claims change, the corresponding domain or security reviewer.
Amendments take effect only after this file is updated and its version and dates
are internally consistent.

Constitution versions follow semantic versioning. A MAJOR increment is required
for removal or incompatible redefinition of a principle or governance duty. A
MINOR increment is required for a new principle or materially expanded mandatory
guidance. A PATCH increment covers clarifications that do not change obligations.
Every review MUST verify constitutional compliance; any justified exception MUST
name the violated rule, owner, scope, expiry date, compensating control, and
removal plan. Permanent undocumented exceptions are prohibited.

**Version**: 1.0.0 | **Ratified**: 2026-08-14 | **Last Amended**: 2026-08-14
