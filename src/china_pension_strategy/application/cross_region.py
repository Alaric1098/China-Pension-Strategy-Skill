"""Cross-region comparison and pension-place determination.

Pure functions over the national pension-place rules and each region's
flexible-employment contribution packages.
"""

from __future__ import annotations

from decimal import Decimal

from china_pension_strategy.application.calculate_months import evaluate_rule
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import PolicyRule

TEN_YEARS_MONTHS = 120


def determine_pension_place(
    place_rules: tuple[PolicyRule, ...],
    *,
    home_region: str,
    current_region: str,
    region_months: dict[str, int],
) -> dict:
    """Determine the pension-drawing place per 国办发〔2009〕66号 第六条."""
    rule = next(
        (r for r in place_rules if r.rule_id == "national-pension-place"), None
    )
    if rule is None:
        raise DomainValidationError("pension-place rule not found")

    relation_in_home = current_region == home_region
    current_over_10 = region_months.get(current_region, 0) >= TEN_YEARS_MONTHS
    prior_over_10 = any(
        months >= TEN_YEARS_MONTHS
        for region, months in region_months.items()
        if region != current_region
    )
    outputs = evaluate_rule(
        rule,
        {
            "relation_in_home_region": relation_in_home,
            "current_region_over_10y": current_over_10,
            "has_prior_region_over_10y": prior_over_10,
        },
    )
    if not outputs or "pension_place_rule" not in outputs:
        raise DomainValidationError("pension-place rule did not produce a decision")
    rule_kind = str(outputs["pension_place_rule"])

    if rule_kind == "HOME_REGION":
        place = home_region
    elif rule_kind == "CURRENT_REGION":
        place = current_region
    elif rule_kind == "PRIOR_OVER10_REGION":
        place = next(
            region
            for region, months in region_months.items()
            if region != current_region and months >= TEN_YEARS_MONTHS
        )
    else:  # HOME_FALLBACK
        place = home_region

    return {
        "place_rule": rule_kind,
        "pension_place": place,
        "home_region": home_region,
        "current_region": current_region,
        "region_months": dict(region_months),
    }


def compare_monthly_contributions(
    rules_by_jurisdiction: dict[str, tuple[PolicyRule, ...]],
    *,
    regions: list[tuple[str, str]],  # (region, jurisdiction)
    contribution_base: Decimal,
) -> list[dict]:
    """Monthly pension contribution per region from its flex package."""
    rows = []
    for region, jurisdiction in regions:
        region_rules = rules_by_jurisdiction.get(jurisdiction, ())
        pension_rule = next(
            (
                r
                for r in region_rules
                if any(
                    f == "monthly_pension_contribution"
                    for result in r.results
                    for f in (result.get("output_field", ""),)
                )
            ),
            None,
        )
        if pension_rule is None:
            rows.append(
                {
                    "region": region,
                    "jurisdiction": jurisdiction,
                    "monthly_pension": None,
                    "status": "UNAVAILABLE",
                }
            )
            continue
        outputs = evaluate_rule(pension_rule, {"contribution_base": str(contribution_base)})
        rows.append(
            {
                "region": region,
                "jurisdiction": jurisdiction,
                "monthly_pension": (
                    str(outputs["monthly_pension_contribution"])
                    if outputs and "monthly_pension_contribution" in outputs
                    else None
                ),
                "status": "AVAILABLE" if outputs else "UNAVAILABLE",
            }
        )
    return rows
