"""Hangzhou flexible-employment region adapter.

Builds the canonical policy queries for Hangzhou flexible-employment analysis
using the Zhejiang provincial layer for contribution rules and
the Hangzhou municipal layer for subsidy rules.
Maps validated person input facts into the domain evidence expected by
the composition use case.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from china_pension_strategy.application.analyze import AnalysisRequest, AnalysisRequestError
from china_pension_strategy.application.resolve_policy import PolicyQuery
from china_pension_strategy.domain.policy import AnalysisMode, JurisdictionRole
from china_pension_strategy.domain.reconciliation import AggregatedCount, ContributionMonth
from china_pension_strategy.domain.values import RoundingMode, YearMonth

SCHEME = "enterprise_employee_basic_pension"
JURISDICTION = "CN-3301"
NATIONAL_JURISDICTION = "CN"
PROVINCE_JURISDICTION = "CN-33"
POPULATION_FLEX = "zhejiang flexible employment participants"
POPULATION_ENTERPRISE = "enterprise participants"
POPULATION_SUBSIDY = "hangzhou employment-difficulty flexible employment participants"


class RegionMappingError(Exception):
    """Safe failure for person-input fact mapping."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class HangzhouRegionAdapter:
    """Canonical Hangzhou flexible-employment queries and fact mapping."""

    def __init__(
        self,
        engine_version: str = "0.1.0",
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
    ) -> tuple[PolicyQuery, ...]:
        """Return the canonical query set for Hangzhou flexible employment."""
        common = {
            "as_of_effective_date": as_of_effective_date,
            "as_known_at": as_known_at,
            "engine_version": self._engine_version,
            "analysis_mode": analysis_mode,
        }
        return (
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
                jurisdiction=PROVINCE_JURISDICTION,
                jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                population_scope=POPULATION_FLEX,
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
        )

    def to_analysis_request(
        self,
        person_input: Mapping[str, object],
    ) -> AnalysisRequest:
        """Map a validated person-input record into an analysis request."""
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
                ),
                month_entries=tuple(month_entries),
                aggregate_counts=tuple(aggregates),
                contribution_base=contribution_base,
                subsidy_inputs=subsidy_inputs,
                requested_capabilities=capabilities,
                rounding=self._rounding,
            )
        except AnalysisRequestError as error:
            raise RegionMappingError("REGION_MAPPING_INVALID", str(error)) from error
