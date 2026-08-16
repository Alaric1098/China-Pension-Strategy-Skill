"""Composition use case: reconcile, resolve, calculate, scenario, recommend.

The use case is deterministic: every digest is computed from request content
only, so identical requests produce identical run IDs. `created_at` is never
part of any digest.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from time import perf_counter_ns
from typing import Any, cast

from china_pension_strategy.application.analyze_scenarios import (
    generate_scenario,
    rank_scenarios,
    select_recommended,
)
from china_pension_strategy.application.calculate_months import (
    assess_subsidy,
    evaluate_rule,
    gap_from_rule,
)
from china_pension_strategy.application.cross_region import (
    compare_monthly_contributions,
    determine_pension_place,
)
from china_pension_strategy.application.estimate_pension import estimate_pension
from china_pension_strategy.application.recommend import build_recommendation
from china_pension_strategy.application.reconcile_records import (
    ReconcileRequest,
    reconcile_contribution_records,
)
from china_pension_strategy.application.resolve_policy import (
    PolicyQuery,
    PolicyVersionNotFoundError,
)
from china_pension_strategy.domain.benefit import PensionEstimate
from china_pension_strategy.domain.calculation import SubsidyAssessment
from china_pension_strategy.domain.eligibility import CapabilityStatus, EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import (
    AnalysisMode,
    PolicyPackage,
    PolicyRule,
    ReviewStatus,
)
from china_pension_strategy.domain.reconciliation import (
    AggregatedCount,
    ContributionMonth,
    ReconcileResult,
)
from china_pension_strategy.domain.run import (
    MANIFEST_VERSION,
    AnalysisRun,
    ComponentVersions,
    RulesetReference,
)
from china_pension_strategy.domain.scenario import (
    ActionType,
    Assumption,
    Recommendation,
    Scenario,
    ScenarioAction,
    Threshold,
)
from china_pension_strategy.domain.values import (
    Money,
    RoundingMode,
    YearMonth,
    YearMonthRange,
)
from china_pension_strategy.ports.outbound.clock import Clock
from china_pension_strategy.ports.outbound.policy_repository import PolicyRepository
from china_pension_strategy.ports.outbound.run_repository import RunRepository
from china_pension_strategy.version import PACKAGE_VERSION

CNY = "CNY"
OUTPUT_SCHEMA_VERSION = "2.0.0"
INPUT_SCHEMA_VERSION = "1.0.0"
ROUNDING_PROFILE = "CNY-half-up-v1"
VALIDATION_SUITE = "architecture-and-domain-v1"


class AnalysisRequestError(DomainValidationError):
    """Raised when the analysis request is structurally invalid."""


@dataclass(frozen=True)
class AnalysisRequest:
    """Full inputs for one deterministic pension analysis run."""

    case_id: str
    scheme: str
    jurisdiction: str
    population_scope: str
    as_of_effective_date: date
    as_known_at: datetime
    engine_version: str
    analysis_mode: AnalysisMode
    policy_queries: tuple[PolicyQuery, ...]
    month_entries: tuple[ContributionMonth, ...] = ()
    aggregate_counts: tuple[AggregatedCount, ...] = ()
    contribution_base: Decimal | None = None
    subsidy_inputs: Mapping[str, object] = field(default_factory=dict)
    pension_inputs: Mapping[str, object] = field(default_factory=dict)
    account_as_of_year_month: YearMonth | None = None
    requested_capabilities: tuple[str, ...] = ()
    horizon: YearMonthRange | None = None
    rounding: RoundingMode = RoundingMode.HALF_UP
    objective: str = "MINIMUM_COMPLIANCE_COST"
    thresholds: tuple[Threshold, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    invalidators: tuple[str, ...] = ("Official account record changes.",)
    review_triggers: tuple[str, ...] = ("Policy package updates.",)

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise AnalysisRequestError("case_id must be a non-empty string")
        for field_name in ("scheme", "jurisdiction", "population_scope"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise AnalysisRequestError(f"{field_name} must be a non-empty string")
        if not self.policy_queries:
            raise AnalysisRequestError("policy_queries cannot be empty")
        if not isinstance(self.as_of_effective_date, date) or isinstance(
            self.as_of_effective_date, datetime
        ):
            raise AnalysisRequestError("as_of_effective_date must be a plain date")
        if not isinstance(self.as_known_at, datetime) or self.as_known_at.tzinfo is None:
            raise AnalysisRequestError("as_known_at must be a timezone-aware datetime")
        if not isinstance(self.analysis_mode, AnalysisMode):
            raise AnalysisRequestError("analysis_mode must be an AnalysisMode")
        if not isinstance(self.rounding, RoundingMode):
            raise AnalysisRequestError("rounding must be a RoundingMode")


@dataclass(frozen=True)
class AnalysisResult:
    """Deterministic outcome of one analysis run."""

    run: AnalysisRun
    output: dict[str, object]
    scenarios: tuple[Scenario, ...]
    recommendation: Recommendation | None
    envelope_status: str = "success"
    warnings: tuple[str, ...] = ()


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, Money):
        return {"amount": str(value.amount), "currency": value.currency}
    if isinstance(value, YearMonth):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (ReconcileResult, SubsidyAssessment)):
        return _canonical(asdict(value))
    return value


def content_digest(value: object) -> str:
    """Return the sha256 digest of the canonical JSON projection of value."""
    canonical = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _review_statuses(mode: AnalysisMode) -> tuple[ReviewStatus, ...]:
    if mode is AnalysisMode.PRODUCTION:
        return (ReviewStatus.PRODUCTION_APPROVED,)
    return (ReviewStatus.MVP_REVIEWED,)


def _ruleset_references(
    packages: Sequence[PolicyPackage],
) -> tuple[RulesetReference, ...]:
    references = []
    for package in packages:
        references.append(
            RulesetReference(
                package_id=package.package_id,
                ruleset_id=package.package_id,
                version=package.version,
                digest=package.content_digest,
            )
        )
    return tuple(
        sorted(
            references,
            key=lambda reference: (reference.package_id, reference.version),
        )
    )


def _scoped_packages(
    repository: PolicyRepository,
    request: AnalysisRequest,
) -> tuple[PolicyPackage, ...]:
    """Collect packages matching the request scope and bitemporal validity.

    Complementary rulesets (for example pension, medical, and unemployment
    contributions) all survive; single-winner precedence is a policy-adapter
    concern and is intentionally not applied here.
    """
    wanted = {(query.scheme, query.topic, query.jurisdiction) for query in request.policy_queries}
    scoped = [
        package
        for package in repository.list_packages()
        if (package.scheme, package.topic, package.jurisdiction) in wanted
        and package.applies_at(request.as_of_effective_date, request.as_known_at)
    ]
    if not scoped:
        raise PolicyVersionNotFoundError("no policy package matches scope and time")
    return tuple(sorted(scoped, key=lambda package: package.package_id))


def _output_fields(rule: PolicyRule) -> tuple[str, ...]:
    return tuple(cast(str, result.get("output_field", "")) for result in rule.results)


def _requirement_rule(
    packages: Sequence[PolicyPackage],
) -> tuple[PolicyRule, str]:
    rules = [
        rule
        for package in packages
        for rule in package.rules
        if any(field in ("minimum_months", "requirement_months") for field in _output_fields(rule))
    ]
    if len(rules) != 1:
        raise AnalysisRequestError(
            "exactly one package rule must produce the minimum-months requirement"
        )
    rule = rules[0]
    field = (
        "requirement_months" if "requirement_months" in _output_fields(rule) else "minimum_months"
    )
    return rule, field


def _contribution_rules(
    packages: Sequence[PolicyPackage],
) -> tuple[PolicyRule, ...]:
    rules = [
        rule
        for package in packages
        for rule in package.rules
        if any(
            field.startswith("monthly_") and field.endswith("_contribution")
            for field in _output_fields(rule)
        )
    ]
    return tuple(sorted(rules, key=lambda rule: rule.rule_id))


def _base_limits_warnings(
    packages: Sequence[PolicyPackage],
    contribution_base: Decimal | None,
) -> tuple[str, ...]:
    """Non-blocking warnings when the declared base sits outside published
    contribution-base floors/ceilings.

    The engine deliberately does not clamp or reject: the amount is still
    computed from the declared base so existing run_ids stay stable, and the
    warning makes the out-of-range assumption explicit in the envelope.
    """
    if contribution_base is None:
        return ()
    warnings: list[str] = []
    for package in packages:
        if package.topic != "flexible_employment_contribution":
            continue
        for rule in package.rules:
            parameters = rule.parameters
            floor = cast(Mapping[str, object] | None, parameters.get("base_floor"))
            ceiling = cast(Mapping[str, object] | None, parameters.get("base_ceiling"))
            if floor is not None and contribution_base < Decimal(str(floor["value"])):
                warnings.append(
                    f"CONTRIBUTION_BASE_BELOW_FLOOR: {package.package_id} "
                    f"declared base {contribution_base} is below the published "
                    f"floor {floor['value']}; result uses the declared base."
                )
            if ceiling is not None and contribution_base > Decimal(str(ceiling["value"])):
                warnings.append(
                    f"CONTRIBUTION_BASE_ABOVE_CEILING: {package.package_id} "
                    f"declared base {contribution_base} is above the published "
                    f"ceiling {ceiling['value']}; result uses the declared base."
                )
            medical_floor = cast(Mapping[str, object] | None, parameters.get("medical_base_floor"))
            medical_ceiling = cast(
                Mapping[str, object] | None, parameters.get("medical_base_ceiling")
            )
            if medical_floor is not None and contribution_base < Decimal(
                str(medical_floor["value"])
            ):
                warnings.append(
                    f"CONTRIBUTION_BASE_BELOW_MEDICAL_FLOOR: {package.package_id} "
                    f"declared base {contribution_base} is below the medical "
                    f"floor {medical_floor['value']}; medical contribution uses "
                    f"the declared base."
                )
            if medical_ceiling is not None and contribution_base > Decimal(
                str(medical_ceiling["value"])
            ):
                warnings.append(
                    f"CONTRIBUTION_BASE_ABOVE_MEDICAL_CEILING: {package.package_id} "
                    f"declared base {contribution_base} is above the medical "
                    f"ceiling {medical_ceiling['value']}; medical contribution uses "
                    f"the declared base."
                )
    return tuple(sorted(set(warnings)))


def _benefit_rules(
    packages: Sequence[PolicyPackage],
) -> tuple[PolicyRule, ...]:
    """Collect rules from the pension-benefit packages (topic pension_benefit_estimation)."""
    return tuple(
        rule
        for package in packages
        if package.topic == "pension_benefit_estimation"
        for rule in package.rules
    )


def _run_estimate(
    request: AnalysisRequest,
    benefit_rules: tuple[PolicyRule, ...],
    average_contribution_index: Decimal,
) -> PensionEstimate:
    """Run one pension estimate with a given average contribution index."""
    return estimate_pension(
        benefit_rules,
        birth=YearMonth(
            int(cast(int, request.pension_inputs["birth_year"])),
            int(cast(int, request.pension_inputs["birth_month"])),
        ),
        gender_category=str(request.pension_inputs["gender_category"]),
        total_contribution_months=int(
            cast(int, request.pension_inputs["total_contribution_months"])
        ),
        average_contribution_index=average_contribution_index,
        account_balance=Money(Decimal(str(request.pension_inputs["account_balance"])), CNY),
        account_as_of=request.account_as_of_year_month or _as_of_month(request),
        c_ping_override=(
            Decimal(str(request.pension_inputs["c_ping_override"]))
            if "c_ping_override" in request.pension_inputs
            else None
        ),
        interest_rate_override=(
            Decimal(str(request.pension_inputs["interest_rate_override"]))
            if "interest_rate_override" in request.pension_inputs
            else None
        ),
        deemed_years=(
            Decimal(str(request.pension_inputs["deemed_years"]))
            if "deemed_years" in request.pension_inputs
            else None
        ),
        transition_years_98=(
            Decimal(str(request.pension_inputs["transition_years_98"]))
            if "transition_years_98" in request.pension_inputs
            else None
        ),
    )


def _pension_estimate_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
) -> dict | None:
    """Build the pension_estimation output section, or None when not applicable."""
    if "PENSION_ESTIMATION" not in request.requested_capabilities:
        return None
    if not request.pension_inputs:
        return None
    benefit_rules = _benefit_rules(packages)
    if not benefit_rules:
        return None
    try:
        estimate = _run_estimate(
            request,
            benefit_rules,
            Decimal(str(request.pension_inputs["average_contribution_index"])),
        )
    except (DomainValidationError, KeyError, TypeError, ValueError):
        return None
    return _serialize_estimate(estimate)


def _sensitivity_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
) -> dict | None:
    """Sensitivity matrix over average-contribution-index tiers."""
    if "SENSITIVITY_ANALYSIS" not in request.requested_capabilities:
        return None
    if not request.pension_inputs:
        return None
    benefit_rules = _benefit_rules(packages)
    if not benefit_rules:
        return None
    tiers_raw = request.pension_inputs.get("sensitivity_index_tiers")
    if not tiers_raw:
        return None
    rows = []
    for tier in cast(tuple[object, ...], tiers_raw):
        try:
            estimate = _run_estimate(request, benefit_rules, Decimal(str(tier)))
        except (DomainValidationError, KeyError, TypeError, ValueError):
            continue
        rows.append(
            {
                "average_index": str(tier),
                "monthly_basic_pension": (
                    str(estimate.monthly_basic_pension.amount)
                    if estimate.monthly_basic_pension is not None
                    else None
                ),
                "monthly_total": (
                    str(estimate.monthly_total.amount)
                    if estimate.monthly_total is not None
                    else None
                ),
            }
        )
    if not rows:
        return None
    return {"index_tiers": rows}


def _money(value: Money | None) -> dict | None:
    if value is None:
        return None
    return {"amount": str(value.amount), "currency": value.currency}


def _serialize_estimate(estimate) -> dict:
    statutory = estimate.statutory
    return {
        "statutory_retirement": {
            "birth": str(statutory.birth),
            "gender_category": statutory.gender_category,
            "delay_months": statutory.delay_months,
            "retirement": str(statutory.retirement),
            "age_months": statutory.age_months,
        },
        "payment_months": str(estimate.payment_months),
        "c_ping": _money(estimate.c_ping),
        "c_ping_year": estimate.c_ping_year,
        "record_interest_rate": str(estimate.record_interest_rate),
        "account_balance": _money(estimate.account_balance),
        "stored_balance": _money(estimate.stored_balance),
        "monthly_basic_pension": _money(estimate.monthly_basic_pension),
        "monthly_account_pension": _money(estimate.monthly_account_pension),
        "monthly_transition_pension": _money(estimate.monthly_transition_pension),
        "monthly_total": _money(estimate.monthly_total),
        "assumptions": [
            {
                "name": assumption.name,
                "value": str(assumption.value),
                "source_type": assumption.source_type,
                "source_refs": list(assumption.source_refs),
                "note": assumption.note,
            }
            for assumption in estimate.assumptions
        ],
    }


def _back_payment_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
) -> dict | None:
    """Build the back_payment output section, or None when not applicable."""
    if "BACK_PAYMENT" not in request.requested_capabilities:
        return None
    back_rules = [
        rule for package in packages if package.topic == "back_payment" for rule in package.rules
    ]
    if not back_rules:
        return None
    year = request.as_of_effective_date.year
    schedule = None
    options = None
    for rule in back_rules:
        if rule.rule_id == "national-minimum-years-schedule":
            outputs = evaluate_rule(rule, {"retirement_year": year})
            if outputs and "minimum_months_at_year" in outputs:
                months = int(cast(int, outputs["minimum_months_at_year"]))
                schedule = {
                    "retirement_year": year,
                    "minimum_months": months,
                    "years": round(months / 12, 1),
                }
        elif rule.rule_id == "national-insufficient-years-options":
            outputs = evaluate_rule(rule, {"months_to_minimum": 0})
            if outputs:
                options = {
                    "extend_payment": bool(outputs.get("option_extend_payment", False)),
                    "lump_sum_payment": bool(outputs.get("option_lump_sum_payment", False)),
                }
    if schedule is None and options is None:
        return None
    return {"minimum_years_schedule": schedule, "options": options}


def _residents_pension_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
) -> dict | None:
    """Build the residents_pension output section, or None when not applicable."""
    if "RESIDENTS_PENSION" not in request.requested_capabilities:
        return None
    residents_rules = [
        rule
        for package in packages
        if package.topic == "residents_pension"
        for rule in package.rules
    ]
    if not residents_rules:
        return None
    basic = None
    for rule in residents_rules:
        if rule.rule_id == "residents-basic-pension":
            outputs = evaluate_rule(rule, {"months": 1})
            if outputs and "monthly_basic_pension" in outputs:
                basic = str(outputs["monthly_basic_pension"])
    balance = request.pension_inputs.get("residents_account_balance")
    account = None
    total = None
    if balance is not None:
        for rule in residents_rules:
            if rule.rule_id == "residents-account-formula":
                outputs = evaluate_rule(rule, {"stored_balance": str(balance)})
                if outputs and "monthly_account_pension" in outputs:
                    account = str(outputs["monthly_account_pension"])
        if basic is not None and account is not None:
            total = str((Decimal(basic) + Decimal(account)).quantize(Decimal("0.01")))
    return {
        "basic_pension": basic,
        "payment_coefficient": 139,
        "account_pension": account,
        "monthly_total": total,
    }


def _cross_region_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
    policy_repository: PolicyRepository,
) -> dict | None:
    """Build the cross_region_comparison output section, or None when not applicable."""
    if "CROSS_REGION_COMPARISON" not in request.requested_capabilities:
        return None
    if not request.pension_inputs:
        return None
    region_months_raw = request.pension_inputs.get("region_contribution_months", ())
    home = str(request.pension_inputs.get("home_region", ""))
    current = str(request.pension_inputs.get("current_region", ""))
    regions = cast(tuple[object, ...], request.pension_inputs.get("comparison_regions", ()))
    has_place_inputs = bool(home and current and region_months_raw)
    has_comparison_inputs = bool(request.contribution_base is not None and regions)
    if not has_place_inputs and not has_comparison_inputs:
        return None
    comparison: dict[str, Any] = {}
    if has_place_inputs:
        try:
            place_rules = tuple(
                rule
                for package in packages
                if package.topic == "pension_place"
                for rule in package.rules
            )
            region_months = {
                str(item["region"]): int(cast(int, item["months"]))
                for item in cast(tuple[Mapping[str, object], ...], region_months_raw)
            }
            comparison["pension_place"] = determine_pension_place(
                place_rules,
                home_region=home,
                current_region=current,
                region_months=region_months,
            )
        except (DomainValidationError, KeyError, TypeError, ValueError):
            comparison["pension_place"] = None

    # Contribution rules live in the province layer for tier-2 cities
    # (chengdu -> sichuan CN-51, etc.); municipalities are single-level.
    jurisdiction_map = {
        "beijing": "CN-11",
        "shanghai": "CN-31",
        "guangzhou": "CN-4401",
        "shenzhen": "CN-4403",
        "hangzhou": "CN-33",
        "chengdu": "CN-51",
        "wuhan": "CN-42",
        "nanjing": "CN-32",
        "tianjin": "CN-12",
        "chongqing": "CN-50",
    }
    if has_comparison_inputs:
        try:
            wanted_jurisdictions = {jurisdiction_map[str(r)] for r in regions}
            rules_by_jurisdiction: dict[str, tuple[PolicyRule, ...]] = {}
            for package in policy_repository.list_packages():
                if (
                    package.scheme == "enterprise_employee_basic_pension"
                    and package.topic == "flexible_employment_contribution"
                    and package.jurisdiction in wanted_jurisdictions
                ):
                    rules_by_jurisdiction[package.jurisdiction] = package.rules
            comparison["region_comparison"] = compare_monthly_contributions(
                rules_by_jurisdiction,
                regions=[(str(r), jurisdiction_map[str(r)]) for r in regions],
                contribution_base=cast(Decimal, request.contribution_base),
            )
        except (DomainValidationError, KeyError, TypeError, ValueError):
            comparison["region_comparison"] = None
    if not any(value not in (None, [], {}) for value in comparison.values()):
        return None
    return comparison


def _personal_pension_tax_output(
    request: AnalysisRequest,
    packages: Sequence[PolicyPackage],
) -> dict | None:
    """Personal pension tax saving estimate, or None when not applicable."""
    if "PERSONAL_PENSION_TAX" not in request.requested_capabilities:
        return None
    if not request.pension_inputs:
        return None
    tax_rules = [
        rule
        for package in packages
        if package.topic == "personal_pension_tax"
        for rule in package.rules
    ]
    if not tax_rules:
        return None
    limit = None
    withdrawal_rate = None
    for rule in tax_rules:
        outputs = evaluate_rule(rule, {"months": 12})
        if not outputs:
            continue
        if "annual_contribution_limit" in outputs:
            limit = Decimal(str(outputs["annual_contribution_limit"]))
        if "withdrawal_tax_rate" in outputs:
            withdrawal_rate = Decimal(str(outputs["withdrawal_tax_rate"]))
    if limit is None or withdrawal_rate is None:
        return None
    try:
        contribution = Decimal(
            str(request.pension_inputs.get("personal_pension_annual_contribution", "0"))
        )
        marginal = Decimal(str(request.pension_inputs.get("marginal_tax_rate", "0")))
        years = int(cast(int, request.pension_inputs.get("personal_pension_years", 0)))
    except (TypeError, ValueError):
        return None
    deductible = min(contribution, limit)
    annual_tax_saving = deductible * marginal
    accumulated = deductible * Decimal(years)
    withdrawal_tax = accumulated * withdrawal_rate
    return {
        "annual_contribution_limit": str(limit),
        "deductible_contribution": str(deductible),
        "marginal_tax_rate": str(marginal),
        "annual_tax_saving": str(annual_tax_saving.quantize(Decimal("0.01"))),
        "withdrawal_tax_rate": str(withdrawal_rate),
        "withdrawal_tax_on_accumulated": str(withdrawal_tax.quantize(Decimal("0.01"))),
        "years": years,
        "note": "税优测算口径（缴费税前扣除 + 领取 3% 单独计税）；不推荐具体产品",
    }


def _requested_capability_statuses(
    request: AnalysisRequest,
    optional_outputs: Mapping[str, object | None],
) -> tuple[dict[str, CapabilityStatus], tuple[str, ...]]:
    statuses = {
        capability: CapabilityStatus.AVAILABLE for capability in request.requested_capabilities
    }
    warnings: list[str] = []
    for capability, value in optional_outputs.items():
        if capability not in statuses or value is not None:
            continue
        statuses[capability] = CapabilityStatus.PARTIAL
        warnings.append(
            f"CAPABILITY_PARTIAL: {capability} was requested but no output was "
            "produced because required inputs or applicable policy rules were "
            "missing or invalid."
        )
    return statuses, tuple(warnings)


def _subsidy_rules(
    packages: Sequence[PolicyPackage],
) -> tuple[PolicyRule, ...]:
    rules = [
        rule
        for package in packages
        for rule in package.rules
        if any(
            field.startswith("subsidy_") or field.startswith("monthly_subsidy_")
            for field in _output_fields(rule)
        )
    ]
    return tuple(sorted(rules, key=lambda rule: rule.rule_id))


def _as_of_month(request: AnalysisRequest) -> YearMonth:
    return YearMonth(request.as_of_effective_date.year, request.as_of_effective_date.month)


def _default_horizon(request: AnalysisRequest) -> YearMonthRange:
    if request.horizon is not None:
        return request.horizon
    as_of_month = _as_of_month(request)
    return YearMonthRange(as_of_month, as_of_month)


def _scenarios(
    request: AnalysisRequest,
    requirement_rule: PolicyRule,
    requirement_field: str,
    contribution_rules: tuple[PolicyRule, ...],
    subsidy_assessment: SubsidyAssessment | None,
    confirmed_months: int,
) -> tuple[Scenario, ...]:
    as_of_month = _as_of_month(request)
    gap = gap_from_rule(
        requirement_rule,
        confirmed_months,
        as_of_month,
        requirement_field=requirement_field,
    )
    horizon = _default_horizon(request)
    actions: tuple[ScenarioAction, ...] = (
        ScenarioAction(month=as_of_month, action_type=ActionType.STOP_CONTRIBUTING),
    )
    stop = generate_scenario(
        scenario_id="stop",
        horizon=horizon,
        actions=actions,
        contribution_rules=None,
        contribution_base=None,
        subsidy_assessment=None,
        rounding=request.rounding,
        confirmed_months=confirmed_months,
        requirement_months=gap.requirement_months,
        capability_refs=("CONTRIBUTION_GAP",),
        thresholds=request.thresholds,
    )
    scenarios = [stop]

    wants_contribution = "FLEXIBLE_EMPLOYMENT_CONTRIBUTION" in request.requested_capabilities
    wants_subsidy = "SUBSIDY_TIMING" in request.requested_capabilities
    if wants_contribution and contribution_rules and request.contribution_base is not None:
        continue_actions = (
            ScenarioAction(month=as_of_month, action_type=ActionType.CONTINUE_CONTRIBUTING),
        )
        scenarios.append(
            generate_scenario(
                scenario_id="continue",
                horizon=horizon,
                actions=continue_actions,
                contribution_rules=contribution_rules,
                contribution_base=request.contribution_base,
                subsidy_assessment=None,
                rounding=request.rounding,
                confirmed_months=confirmed_months,
                requirement_months=gap.requirement_months,
                capability_refs=("CONTRIBUTION_GAP", "FLEXIBLE_EMPLOYMENT_CONTRIBUTION"),
                thresholds=request.thresholds,
            )
        )
        if (
            wants_subsidy
            and subsidy_assessment is not None
            and subsidy_assessment.status is EligibilityStatus.ELIGIBLE
        ):
            scenarios.append(
                generate_scenario(
                    scenario_id="subsidized",
                    horizon=horizon,
                    actions=(
                        ScenarioAction(
                            month=as_of_month,
                            action_type=ActionType.CONTINUE_CONTRIBUTING,
                        ),
                        ScenarioAction(
                            month=as_of_month,
                            action_type=ActionType.APPLY_FOR_SUBSIDY,
                        ),
                    ),
                    contribution_rules=contribution_rules,
                    contribution_base=request.contribution_base,
                    subsidy_assessment=subsidy_assessment,
                    rounding=request.rounding,
                    confirmed_months=confirmed_months,
                    requirement_months=gap.requirement_months,
                    capability_refs=(
                        "CONTRIBUTION_GAP",
                        "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
                        "SUBSIDY_ELIGIBILITY",
                        "SUBSIDY_TIMING",
                    ),
                    thresholds=request.thresholds,
                    sensitivity={
                        "assumption_refs": tuple(
                            assumption.assumption_id for assumption in request.assumptions
                        )
                    },
                )
            )
    return tuple(scenarios)


def analyze(
    request: AnalysisRequest,
    policy_repository: PolicyRepository,
    run_repository: RunRepository,
    clock: Clock,
    initial_warnings: Sequence[str] = (),
) -> AnalysisResult:
    """Run one deterministic analysis end to end and store the run."""
    started_at_ns = perf_counter_ns()
    reconciliation = reconcile_contribution_records(
        ReconcileRequest(
            scheme=request.scheme,
            month_entries=request.month_entries,
            aggregate_counts=request.aggregate_counts,
        )
    )
    packages = _scoped_packages(policy_repository, request)
    requirement_rule, requirement_field = _requirement_rule(packages)
    contribution_rules = _contribution_rules(packages)
    subsidy_rules = _subsidy_rules(packages)

    subsidy_assessment = None
    if subsidy_rules:
        subsidy_assessment = assess_subsidy(
            subsidy_rules,
            request.subsidy_inputs,
            _as_of_month(request),
            request.rounding,
        )

    scenarios = _scenarios(
        request,
        requirement_rule,
        requirement_field,
        contribution_rules,
        subsidy_assessment,
        reconciliation.confirmed_months,
    )
    ranked = rank_scenarios(scenarios, objective=request.objective)
    pension_estimation = _pension_estimate_output(request, packages)
    back_payment = _back_payment_output(request, packages)
    residents_pension = _residents_pension_output(request, packages)
    cross_region = _cross_region_output(request, packages, policy_repository)
    sensitivity = _sensitivity_output(request, packages)
    personal_pension_tax = _personal_pension_tax_output(request, packages)
    capability_statuses, capability_warnings = _requested_capability_statuses(
        request,
        {
            "RETIREMENT_AGE": (
                pension_estimation.get("statutory_retirement")
                if isinstance(pension_estimation, Mapping)
                else None
            ),
            "PENSION_ESTIMATION": pension_estimation,
            "BACK_PAYMENT": back_payment,
            "RESIDENTS_PENSION": residents_pension,
            "CROSS_REGION_COMPARISON": cross_region,
            "SENSITIVITY_ANALYSIS": sensitivity,
            "PERSONAL_PENSION_TAX": personal_pension_tax,
        },
    )
    recommendation = None
    if "RECOMMENDATION" in request.requested_capabilities:
        try:
            recommended = select_recommended(ranked)
            base_limitations = [
                "This analysis is a local informational MVP only.",
                "It is not legal, tax, or financial advice.",
            ]
            # Policy-version awareness: surface packages AND rules whose
            # validity ends soon so the conclusion's window is explicit.
            # Rule-level expiry matters when a source document's validity
            # boundary ends before the package does (e.g. Guangzhou medical
            # rate valid until 2026-12-31).
            seen_packages: set[str] = set()
            for package in packages:
                end = package.effective_to
                if end is not None:
                    months_left = (end.year - request.as_of_effective_date.year) * 12 + (
                        end.month - request.as_of_effective_date.month
                    )
                    if 0 <= months_left <= 18 and package.package_id not in seen_packages:
                        seen_packages.add(package.package_id)
                        base_limitations.append(
                            f"Policy version {package.package_id} expires "
                            f"{end.isoformat()}; conclusions rest on that rule version."
                        )
                for rule in package.rules:
                    rule_end = rule.effective_to
                    if rule_end is None:
                        continue
                    months_left = (rule_end.year - request.as_of_effective_date.year) * 12 + (
                        rule_end.month - request.as_of_effective_date.month
                    )
                    if 0 <= months_left <= 18:
                        base_limitations.append(
                            f"Rule {package.package_id}/{rule.rule_id} expires "
                            f"{rule_end.isoformat()}; conclusions rest on that rule version."
                        )
            recommendation = build_recommendation(
                recommended,
                objective=request.objective,
                capability_dependencies=(
                    {
                        "capability_id": capability,
                        "status": capability_statuses[capability].value,
                    }
                    for capability in request.requested_capabilities
                ),
                limitations=tuple(base_limitations),
                invalidators=request.invalidators,
                review_triggers=request.review_triggers,
            )
        except DomainValidationError:
            recommendation = None

    scenarios_by_id = {scenario.scenario_id: scenario for scenario in ranked}
    output = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "case_id": request.case_id,
        "scheme": request.scheme,
        "as_of": request.as_of_effective_date.isoformat(),
        "reconciliation": _scenario_output(reconciliation),
        "scenarios": {
            scenario_id: _scenario_output(scenario)
            for scenario_id, scenario in sorted(scenarios_by_id.items())
        },
        "recommendation": _scenario_output(recommendation),
    }
    if capability_warnings:
        output["capability_statuses"] = {
            capability: status.value for capability, status in capability_statuses.items()
        }
    if pension_estimation is not None:
        output["pension_estimation"] = pension_estimation
    if back_payment is not None:
        output["back_payment"] = back_payment
    if residents_pension is not None:
        output["residents_pension"] = residents_pension
    if cross_region is not None:
        output["cross_region_comparison"] = cross_region
    if sensitivity is not None:
        output["sensitivity_analysis"] = sensitivity
    if personal_pension_tax is not None:
        output["personal_pension_tax"] = personal_pension_tax

    input_digest = content_digest(
        {
            "case_id": request.case_id,
            "scheme": request.scheme,
            "jurisdiction": request.jurisdiction,
            "population_scope": request.population_scope,
            "as_of_effective_date": request.as_of_effective_date,
            "month_entries": [
                (entry.scheme, str(entry.month), entry.source_id) for entry in request.month_entries
            ],
            "aggregate_counts": [
                (entry.scheme, entry.reported_months, entry.source_id)
                for entry in request.aggregate_counts
            ],
            "contribution_base": request.contribution_base,
            "subsidy_inputs": request.subsidy_inputs,
            "requested_capabilities": request.requested_capabilities,
            # Conditional keys: only present when pension inputs exist so
            # existing runs' content-addressed run_ids stay unchanged.
            **({"pension_inputs": request.pension_inputs} if request.pension_inputs else {}),
        }
    )
    assumption_digest = content_digest(
        {
            "thresholds": [
                {
                    "threshold_id": threshold.threshold_id,
                    "metric": threshold.metric,
                    "operator": threshold.operator,
                    "value": threshold.value,
                }
                for threshold in request.thresholds
            ],
            "assumptions": [
                {
                    "assumption_id": assumption.assumption_id,
                    "event_definition": assumption.event_definition,
                    "source_type": assumption.source_type,
                    "modeling_mode": assumption.modeling_mode,
                    "source_date": assumption.source_date,
                }
                for assumption in request.assumptions
            ],
        }
    )
    objective_digest = content_digest(request.objective)
    output_digest = content_digest(output)
    base_warnings = _base_limits_warnings(packages, request.contribution_base)
    warnings = (*initial_warnings, *base_warnings, *capability_warnings)

    run = AnalysisRun(
        parent_run_id=None,
        analysis_mode=request.analysis_mode,
        review_statuses=_review_statuses(request.analysis_mode),
        component_versions=ComponentVersions(
            engine=request.engine_version,
            input_schema=INPUT_SCHEMA_VERSION,
            output_schema=OUTPUT_SCHEMA_VERSION,
            manifest_schema=MANIFEST_VERSION,
            rounding_profile=ROUNDING_PROFILE,
        ),
        policy_rulesets=_ruleset_references(packages),
        input_snapshot_digest=input_digest,
        assumption_set_digest=assumption_digest,
        objective_digest=objective_digest,
        output_digest=output_digest,
        artifact_digests=(),
        adapter_versions={
            "policy_repository": PACKAGE_VERSION,
            "run_repository": PACKAGE_VERSION,
            "clock": PACKAGE_VERSION,
        },
        validation={
            "input_schema_valid": True,
            "policy_schema_valid": True,
            "output_schema_valid": True,
            "invariants_valid": True,
        },
        validation_suite=VALIDATION_SUITE,
        warnings_count=len(warnings),
        unresolved_conflicts_count=len(reconciliation.conflicts),
        duration_ms=(perf_counter_ns() - started_at_ns) // 1_000_000,
        created_at=clock.now_utc(),
    )
    run.mark_succeeded()
    run_repository.save(run)
    return AnalysisResult(
        run=run,
        output=output,
        scenarios=ranked,
        recommendation=recommendation,
        envelope_status=("partial" if capability_warnings else "success"),
        warnings=warnings,
    )


def _scenario_output(value: object) -> object:
    """Project domain outcomes into deterministic JSON-safe structures."""
    if isinstance(value, Scenario):
        return {
            "scenario_id": value.scenario_id,
            "feasibility": value.feasibility.value,
            "capability_refs": list(value.capability_refs),
            "horizon": [str(month) for month in value.horizon],
            "cash_flows": [
                {
                    "month": str(flow.month),
                    "pension": _money_output(flow.pension),
                    "medical": _money_output(flow.medical),
                    "unemployment": _money_output(flow.unemployment),
                    "subsidy": _money_output(flow.subsidy),
                    "net_outflow": _money_output(flow.net_outflow),
                    "cumulative_outflow": _money_output(flow.cumulative_outflow),
                }
                for flow in value.monthly_cash_flows
            ],
            "outcomes": {
                "ending_confirmed_months": value.outcomes.ending_confirmed_months,
                "ending_gap_months": value.outcomes.ending_gap_months,
                "total_pension": _money_output(value.outcomes.total_pension),
                "total_medical": _money_output(value.outcomes.total_medical),
                "total_unemployment": _money_output(value.outcomes.total_unemployment),
                "total_subsidy": _money_output(value.outcomes.total_subsidy),
                "total_net_outflow": _money_output(value.outcomes.total_net_outflow),
            },
        }
    if isinstance(value, Recommendation):
        return {
            "scenario_id": value.scenario_id,
            "objective": value.objective,
            "capability_dependencies": [
                dict(dependency) for dependency in value.capability_dependencies
            ],
            "limitations": list(value.limitations),
            "invalidators": list(value.invalidators),
            "review_triggers": list(value.review_triggers),
        }
    if isinstance(value, ReconcileResult):
        return {
            "scheme": value.scheme,
            "confirmed_months": value.confirmed_months,
            "duplicates": [
                {
                    "scheme": duplicate.scheme,
                    "month": str(duplicate.month),
                    "source_id": duplicate.source_id,
                }
                for duplicate in value.duplicates
            ],
            "conflicts": [
                {
                    "conflict_id": conflict.conflict_id,
                    "fact_scope": conflict.fact_scope,
                    "assertion_refs": list(conflict.assertion_refs),
                    "status": conflict.status.value,
                    "resolution_evidence_refs": list(conflict.resolution_evidence_refs),
                }
                for conflict in value.conflicts
            ],
            "other_scheme_entries": [
                {
                    "scheme": entry.scheme,
                    "month": str(entry.month),
                    "source_id": entry.source_id,
                }
                for entry in value.other_scheme_entries
            ],
        }
    return _canonical(value)


def _money_output(money: Money) -> dict[str, str]:
    return {"amount": str(money.amount), "currency": money.currency}
