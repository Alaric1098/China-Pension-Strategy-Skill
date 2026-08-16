"""Conditional recommendation from ranked scenarios."""

from collections.abc import Iterable, Mapping

from china_pension_strategy.domain.scenario import Recommendation, Scenario


def build_recommendation(
    scenario: Scenario,
    objective: str,
    capability_dependencies: Iterable[Mapping[str, object]],
    assumption_refs: Iterable[str] = (),
    limitations: Iterable[str] = (),
    thresholds: Iterable[str] = (),
    invalidators: Iterable[str] = (),
    review_triggers: Iterable[str] = (),
) -> Recommendation:
    """Wrap the top scenario with governance and invalidation metadata."""
    return Recommendation(
        scenario_id=scenario.scenario_id,
        objective=objective,
        capability_dependencies=tuple(capability_dependencies),
        assumption_refs=tuple(assumption_refs),
        limitations=tuple(limitations),
        thresholds=tuple(thresholds),
        invalidators=tuple(invalidators),
        review_triggers=tuple(review_triggers),
    )
