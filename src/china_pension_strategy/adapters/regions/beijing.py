"""Beijing flexible-employment region adapter.

Builds the canonical policy queries for Beijing flexible-employment analysis
and maps validated person input facts into the domain evidence expected by
the composition use case.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from china_pension_strategy.application.analyze import AnalysisRequest, AnalysisRequestError
from china_pension_strategy.application.resolve_policy import PolicyQuery
from china_pension_strategy.domain.policy import AnalysisMode, JurisdictionRole
from china_pension_strategy.domain.reconciliation import AggregatedCount, ContributionMonth
from china_pension_strategy.domain.values import RoundingMode, YearMonth
from china_pension_strategy.version import ENGINE_SEMANTICS_VERSION

SCHEME = "enterprise_employee_basic_pension"
JURISDICTION = "CN-11"
NATIONAL_JURISDICTION = "CN"
# Covered regions (region name -> jurisdiction) usable in cross-region comparison.
_COMPARISON_REGIONS = (
    ("beijing", "CN-11"),
    ("shanghai", "CN-31"),
    ("guangzhou", "CN-4401"),
    ("shenzhen", "CN-4403"),
    ("hangzhou", "CN-3301"),
    ("chengdu", "CN-5101"),
    ("wuhan", "CN-4201"),
    ("nanjing", "CN-3201"),
    ("tianjin", "CN-12"),
    ("chongqing", "CN-50"),
)
POPULATION_ENTERPRISE = "enterprise participants"
POPULATION_FLEX = "beijing flexible employment participants"
POPULATION_SUBSIDY = "beijing employment-difficulty flexible employment participants"


class RegionMappingError(Exception):
    """Safe failure for person-input fact mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class BeijingRegionAdapter:
    """Canonical Beijing flexible-employment queries and fact mapping."""

    def __init__(
        self,
        engine_version: str = ENGINE_SEMANTICS_VERSION,
        rounding: RoundingMode = RoundingMode.HALF_UP,
    ) -> None:
        self._engine_version = engine_version
        self._rounding = rounding

    def policy_queries(
        self,
        *,
        as_of_effective_date: date,
        as_known_at: datetime,
        analysis_mode: AnalysisMode,
        requested_capabilities: Sequence[str] = (),
        comparison_regions: Sequence[str] = (),
    ) -> tuple[PolicyQuery, ...]:
        """Return the canonical query set for Beijing flexible employment.

        Pension-benefit queries are added only when PENSION_ESTIMATION is
        requested, so existing runs keep identical query scopes and run_ids.
        """
        common: dict[str, Any] = {
            "as_of_effective_date": as_of_effective_date,
            "as_known_at": as_known_at,
            "engine_version": self._engine_version,
            "analysis_mode": analysis_mode,
        }
        queries = [
            PolicyQuery(
                scheme=SCHEME,
                topic="minimum_contribution",
                jurisdiction=NATIONAL_JURISDICTION,
                jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                population_scope=POPULATION_ENTERPRISE,
                **common,
            ),
            PolicyQuery(
                scheme=SCHEME,
                topic="flexible_employment_contribution",
                jurisdiction=JURISDICTION,
                jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                population_scope=POPULATION_FLEX,
                **common,
            ),
            PolicyQuery(
                scheme=SCHEME,
                topic="flexible_employment_subsidy",
                jurisdiction=JURISDICTION,
                jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                population_scope=POPULATION_SUBSIDY,
                **common,
            ),
        ]
        if "PENSION_ESTIMATION" in requested_capabilities:
            queries.append(
                PolicyQuery(
                    scheme=SCHEME,
                    topic="pension_benefit_estimation",
                    jurisdiction=NATIONAL_JURISDICTION,
                    jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                    population_scope=POPULATION_ENTERPRISE,
                    **common,
                )
            )
        if "BACK_PAYMENT" in requested_capabilities:
            queries.append(
                PolicyQuery(
                    scheme=SCHEME,
                    topic="back_payment",
                    jurisdiction=NATIONAL_JURISDICTION,
                    jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                    population_scope=POPULATION_ENTERPRISE,
                    **common,
                )
            )
        if "RESIDENTS_PENSION" in requested_capabilities:
            queries.append(
                PolicyQuery(
                    scheme="residents_pension",
                    topic="residents_pension",
                    jurisdiction=NATIONAL_JURISDICTION,
                    jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                    population_scope="residents participants",
                    **common,
                )
            )
        if "PERSONAL_PENSION_TAX" in requested_capabilities:
            queries.append(
                PolicyQuery(
                    scheme="personal_pension",
                    topic="personal_pension_tax",
                    jurisdiction=NATIONAL_JURISDICTION,
                    jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                    population_scope="individual participants",
                    **common,
                )
            )
        if "CROSS_REGION_COMPARISON" in requested_capabilities:
            queries.append(
                PolicyQuery(
                    scheme=SCHEME,
                    topic="pension_place",
                    jurisdiction=NATIONAL_JURISDICTION,
                    jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                    population_scope=POPULATION_ENTERPRISE,
                    **common,
                )
            )
            queries.append(
                PolicyQuery(
                    scheme=SCHEME,
                    topic="pension_benefit_estimation",
                    jurisdiction=JURISDICTION,
                    jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                    population_scope=POPULATION_ENTERPRISE,
                    **common,
                )
            )
        return tuple(queries)

    def to_analysis_request(
        self,
        person_input: Mapping[str, object],
    ) -> AnalysisRequest:
        """Map a validated person-input record into an analysis request."""
        person_input = cast(dict[str, Any], person_input)
        created_at = datetime.fromisoformat(str(person_input["created_at"]))
        as_of = created_at.date()
        if "analysis_date" in person_input:
            as_of = date.fromisoformat(str(person_input["analysis_date"]))
        analysis_mode = AnalysisMode(str(person_input["analysis_mode"]))
        capabilities = tuple(str(item) for item in person_input["requested_capabilities"])

        month_entries: list[ContributionMonth] = []
        aggregates: list[AggregatedCount] = []
        contribution_base: Decimal | None = None
        subsidy_inputs: dict[str, object] = {}
        pension_inputs: dict[str, object] = {}
        account_as_of: YearMonth | None = None

        for fact in person_input.get("facts", ()):
            fact_type = str(fact["fact_type"])
            source_ref = str(fact["source_ref"])
            value = fact["value"]
            if fact_type == "contribution_base":
                try:
                    contribution_base = Decimal(str(value))
                except (InvalidOperation, ValueError) as error:
                    raise RegionMappingError(
                        "FACT_INVALID_DECIMAL",
                        f"contribution_base fact is not a decimal: {value!r}",
                    ) from error
            elif fact_type == "contribution_month":
                year, month = str(value).split("-")
                month_entries.append(
                    ContributionMonth(
                        scheme=SCHEME,
                        month=YearMonth(int(year), int(month)),
                        source_id=source_ref,
                    )
                )
            elif fact_type == "aggregate_count":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise RegionMappingError(
                        "FACT_INVALID_INTEGER",
                        f"aggregate_count fact is not an integer: {value!r}",
                    )
                aggregates.append(
                    AggregatedCount(
                        scheme=SCHEME,
                        reported_months=value,
                        source_id=source_ref,
                    )
                )
            elif fact_type == "subsidy_input":
                input_id = str(fact["fact_id"])
                raw = fact["value"]
                subsidy_inputs[input_id] = raw
            elif fact_type == "birth_year_month":
                year, month = str(value).split("-")
                pension_inputs["birth_year"] = int(year)
                pension_inputs["birth_month"] = int(month)
            elif fact_type == "gender_category":
                pension_inputs["gender_category"] = str(value)
            elif fact_type == "total_contribution_months":
                pension_inputs["total_contribution_months"] = int(value)
            elif fact_type == "deemed_years":
                pension_inputs["deemed_years"] = Decimal(str(value))
            elif fact_type == "transition_years_98":
                pension_inputs["transition_years_98"] = Decimal(str(value))
            elif fact_type == "average_contribution_index":
                pension_inputs["average_contribution_index"] = Decimal(str(value))
            elif fact_type == "account_balance":
                pension_inputs["account_balance"] = Decimal(str(value))
                try:
                    year, month = str(fact["as_of_date"]).split("-")[:2]
                    account_as_of = YearMonth(int(year), int(month))
                except (KeyError, TypeError, ValueError):
                    account_as_of = None
            elif fact_type == "interest_rate_override":
                pension_inputs["interest_rate_override"] = Decimal(str(value))
            elif fact_type == "c_ping_override":
                pension_inputs["c_ping_override"] = Decimal(str(value))
            elif fact_type == "residents_account_balance":
                pension_inputs["residents_account_balance"] = Decimal(str(value))
            elif fact_type == "home_region":
                pension_inputs["home_region"] = str(value)
            elif fact_type == "current_region":
                pension_inputs["current_region"] = str(value)
            elif fact_type == "comparison_regions":
                if isinstance(value, str):
                    pension_inputs["comparison_regions"] = [
                        item.strip() for item in value.split(",") if item.strip()
                    ]
                else:
                    pension_inputs["comparison_regions"] = list(value)
            elif fact_type == "region_contribution_months":
                if isinstance(value, str):
                    pension_inputs["region_contribution_months"] = json.loads(value)
                else:
                    pension_inputs["region_contribution_months"] = list(value)
            elif fact_type == "sensitivity_index_tiers":
                if isinstance(value, str):
                    pension_inputs["sensitivity_index_tiers"] = json.loads(value)
                else:
                    pension_inputs["sensitivity_index_tiers"] = list(value)
            elif fact_type == "personal_pension_annual_contribution":
                pension_inputs["personal_pension_annual_contribution"] = Decimal(str(value))
            elif fact_type == "marginal_tax_rate":
                pension_inputs["marginal_tax_rate"] = Decimal(str(value))
            elif fact_type == "personal_pension_years":
                pension_inputs["personal_pension_years"] = int(value)

        try:
            return AnalysisRequest(
                case_id=str(person_input["case_id"]),
                scheme=SCHEME,
                jurisdiction=JURISDICTION,
                population_scope=POPULATION_ENTERPRISE,
                as_of_effective_date=as_of,
                as_known_at=created_at,
                engine_version=self._engine_version,
                analysis_mode=analysis_mode,
                policy_queries=self.policy_queries(
                    as_of_effective_date=as_of,
                    as_known_at=created_at,
                    analysis_mode=analysis_mode,
                    requested_capabilities=capabilities,
                    comparison_regions=tuple(
                        cast(tuple[str, ...], pension_inputs.get("comparison_regions", ()))
                    ),
                ),
                month_entries=tuple(month_entries),
                aggregate_counts=tuple(aggregates),
                contribution_base=contribution_base,
                subsidy_inputs=subsidy_inputs,
                pension_inputs=pension_inputs,
                account_as_of_year_month=account_as_of,
                requested_capabilities=capabilities,
                rounding=self._rounding,
            )
        except AnalysisRequestError as error:
            raise RegionMappingError("REGION_MAPPING_INVALID", str(error)) from error
