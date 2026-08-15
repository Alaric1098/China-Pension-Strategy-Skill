# Design Contract Closure

## Goal

Close the gaps identified in the README review without implementing the runtime Skill. The design documents, JSON output schema, and automated audits must describe one consistent, machine-verifiable contract.

## Scope

- Add a three-valued eligibility result: `ELIGIBLE`, `INELIGIBLE`, or `UNKNOWN`.
- Replace globally required intake fields with capability-specific `required_for` requirements.
- Remove the generic subsidy formula from the core engine and define a deterministic rule-evaluation boundary.
- Expose both effective date and known-at time in analysis output.
- Distinguish sourced probabilities from scenario-only assumptions and require non-probabilistic fallback when evidence is absent.
- Define deterministic policy conflict dimensions without mixing general policy with individual official determinations.
- Define privacy actions by processing boundary rather than assigning one global action to a field.
- Raise deterministic, boundary, property, replay, and end-to-end test targets.
- Upgrade architecture auditing from keyword coverage to contract assertions.

## Contract Shape

The structured output remains the single source of truth. It will include an immutable snapshot, eligibility assessments, capability availability, record conflicts, policy ambiguities, scenarios, recommendation, warnings, and errors. The snapshot requires `as_of_effective_date` and `as_known_at`; both values participate in run identity and idempotency.

Each eligibility assessment requires an `assessment_id`, capability and subject scope, one of `ELIGIBLE`, `INELIGIBLE`, or `UNKNOWN`, applicable rule IDs, and condition records. Each condition has a stable ID, status (`SATISFIED`, `FAILED`, or `UNVERIFIED`), fact references, rule references, and a safe explanation. `ELIGIBLE` requires no failed or unverified conditions, `INELIGIBLE` requires at least one failed condition, and `UNKNOWN` requires no failed conditions and at least one unverified condition.

An intake field can be absent without blocking the entire run. Each capability declares its required facts and returns `AVAILABLE`, `PARTIAL`, or `BLOCKED`, with missing and satisfied requirement IDs. `AVAILABLE` has all required facts, `PARTIAL` can produce explicitly bounded output without all precision-enhancing facts, and `BLOCKED` cannot produce that capability's result. Recommendations may depend on `AVAILABLE` capabilities and may conditionally use `PARTIAL` capabilities only when their limitations and invalidators are cited; they never depend on `BLOCKED` capabilities.

Missing facts make the whole run `BLOCKED` only when every requested analytical capability is blocked or a safety/policy prerequisite prevents calculation. A globally blocked run does not create `analysis-output`; its tool envelope has `status: error`, empty `data`, and at least one stable blocking error. Otherwise calculation proceeds. Analysis-output `success` requires all requested capabilities to be `AVAILABLE`; `partial` requires at least one `PARTIAL` or `BLOCKED` capability and at least one warning.

`resolve_policy_rules`, backed by `PolicyRepository`, selects approved, versioned rule packages. `RegionPolicyProvider` supplies jurisdiction enumeration and mappings only. A deterministic evaluator executes `PolicyRule`, `DecisionTable`, and `ParameterTable` objects. Neither the core calculator nor a region adapter hard-codes a nationwide subsidy formula.

Record conflicts require a conflict ID, fact scope, competing assertion references, status, and resolution evidence. Policy ambiguities require an ambiguity ID, requested capability, competing rule IDs, conflict dimensions, and blocking effect. General policy candidates are narrowed by scheme, jurisdiction role, effective time, known-at time, legal hierarchy, explicit `RuleOverride`, compatibility, and publication status. No implicit “more specific” tie-break is allowed. Incompatible remaining outputs produce `AMBIGUOUS_POLICY_RULE` and block affected capabilities. `OfficialDetermination` remains case evidence and never rewrites general rule precedence.

Probability assumptions use `official_statistic`, `user_provided`, `expert_assumption`, or `scenario_only`. Only a current, approved `official_statistic` whose population and event definition match the case may be presented as an evidence-backed probability. Other source types remain labeled assumptions. A point value requires event definition, value/range/distribution, source date, population, provenance, approval, expiry, and dependency treatment. Output records a `modeling_mode` of `EVIDENCE_BACKED_PROBABILITY`, `USER_ASSUMPTION`, `EXPERT_ASSUMPTION`, `SCENARIO_ONLY`, `THRESHOLD`, or `RANGE`. Without qualifying official evidence, recommendations use threshold, range, or conservative/base/optimistic scenarios and must not present a point estimate as observed probability.

## Error And Safety Behavior

Policy ambiguity produces `AMBIGUOUS_POLICY_RULE`; missing facts block only affected capabilities unless no meaningful analysis remains. Individual official determinations remain case evidence and do not overwrite general policy precedence.

Privacy actions are evaluated by data classification, boundary, purpose/consent, and destination. Boundaries are raw evidence intake, normalized facts, logs, external services, and reports; actions are `ALLOW`, `REDACT`, or `BLOCK`. `REDACT` replaces prohibited values with typed placeholders before crossing the boundary. Missing consent, a prohibited destination, or data that cannot be safely minimized produces `BLOCK` and `PRIVACY_POLICY_VIOLATION`. External services retain the stricter authorization, location, training, retention, encryption, and minimum-fragment requirements already defined by the security contract.

| Classification | Raw intake | Normalized facts | Logs | External service | Report |
|---|---|---|---|---|---|
| `S0-PUBLIC` | ALLOW | ALLOW | ALLOW | ALLOW subject to destination policy | ALLOW |
| `S1-INTERNAL` | ALLOW | ALLOW | REDACT to IDs/counts | BLOCK unless explicitly approved | REDACT |
| `S2-CONFIDENTIAL` | ALLOW in case storage | REDACT to calculation-minimum fields | BLOCK raw values | BLOCK by default; REDACT only with explicit consent and approved service | REDACT |
| `S3-RESTRICTED` | ALLOW only in temporary isolation or encrypted evidence store | REDACT; retain only approved derived facts | BLOCK | BLOCK | BLOCK raw values; only non-identifying derived facts may be ALLOWed |

## Verification

The design requires at least 25 deterministic examples, including explicit 59/60/61-month and 179/180/181-month boundaries; at least 5 property invariants; at least 3 dual-time replay cases; and 8 end-to-end evals. Rule packages continue to carry their own approved test vectors.

Automated checks will fail unless the output schema contains the eligibility and capability enums, dual-time snapshot fields, conflicts, policy ambiguities, recommendation capability references, and `partial` warning invariant. Documentation checks will fail unless they define the rule-evaluator boundary, conflict ordering, privacy actions, probability fallback, and the numeric test targets. Existing link, JSON parsing, and sensitive-data checks remain in place.
