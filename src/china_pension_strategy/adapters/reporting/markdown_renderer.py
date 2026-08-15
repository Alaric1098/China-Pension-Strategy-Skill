"""Markdown rendering for analysis runs.

Produces a deterministic, human-readable report from a run and its validated
analysis output. Cash flows are rendered as monthly tables with totals.
"""

from __future__ import annotations

from typing import Any, Mapping

from china_pension_strategy.domain.run import AnalysisRun


def _money(value: object) -> str:
    if isinstance(value, Mapping):
        return f"{value.get('amount', '0.00')} {value.get('currency', 'CNY')}"
    return str(value)


def render_markdown(
    run: AnalysisRun,
    output: Mapping[str, Any],
) -> str:
    """Render a Markdown report for the run and its validated output."""
    lines: list[str] = []
    lines.append("# Pension Strategy Analysis")
    lines.append("")
    lines.append(f"- **Run ID:** `{run.run_id}`")
    lines.append(f"- **Case:** `{output.get('case_id', '')}`")
    lines.append(f"- **Scheme:** `{output.get('scheme', '')}`")
    lines.append(f"- **As of:** {output.get('as_of', '')}")
    lines.append(f"- **Mode:** {run.analysis_mode.value}")
    lines.append("")

    reconciliation = output.get("reconciliation", {})
    lines.append("## Reconciliation")
    lines.append("")
    if isinstance(reconciliation, Mapping):
        lines.append(
            f"- Confirmed months: {reconciliation.get('confirmed_months', 0)}"
        )
        conflicts = reconciliation.get("conflicts", [])
        if conflicts:
            lines.append(f"- Unresolved conflicts: {len(conflicts)}")
        for conflict in conflicts:
            lines.append(f"  - `{conflict.get('conflict_id', '')}`: {conflict.get('status', '')}")
    lines.append("")

    scenarios = output.get("scenarios", {})
    lines.append("## Scenario Comparison")
    lines.append("")
    if isinstance(scenarios, Mapping):
        for scenario_id, scenario in sorted(scenarios.items()):
            if not isinstance(scenario, Mapping):
                continue
            lines.append(f"### {scenario_id}")
            lines.append("")
            lines.append(f"- Feasibility: `{scenario.get('feasibility', '')}`")
            outcomes = scenario.get("outcomes", {})
            if isinstance(outcomes, Mapping):
                lines.append(
                    f"- Ending months: {outcomes.get('ending_confirmed_months', 0)} "
                    f"(gap {outcomes.get('ending_gap_months', 0)})"
                )
                lines.append(
                    f"- Total net outflow: "
                    f"{_money(outcomes.get('total_net_outflow'))}"
                )
            lines.append("")
            lines.append("| Month | Pension | Medical | Unemployment | Subsidy | Net | Cumulative |")
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
            for flow in scenario.get("cash_flows", []):
                if not isinstance(flow, Mapping):
                    continue
                lines.append(
                    f"| {flow.get('month', '')} | "
                    f"{_money(flow.get('pension'))} | "
                    f"{_money(flow.get('medical'))} | "
                    f"{_money(flow.get('unemployment'))} | "
                    f"{_money(flow.get('subsidy'))} | "
                    f"{_money(flow.get('net_outflow'))} | "
                    f"{_money(flow.get('cumulative_outflow'))} |"
                )
            lines.append("")

    estimation = output.get("pension_estimation")
    if isinstance(estimation, Mapping):
        lines.append("## Pension Estimation")
        lines.append("")
        statutory = estimation.get("statutory_retirement", {})
        if isinstance(statutory, Mapping):
            lines.append(
                f"- Statutory retirement: {statutory.get('retirement', '')} "
                f"(delay {statutory.get('delay_months', 0)} months)"
            )
        lines.append(f"- Payment months: {estimation.get('payment_months', '')}")
        c_ping = estimation.get("c_ping")
        if isinstance(c_ping, Mapping):
            lines.append(
                f"- C_ping ({estimation.get('c_ping_year', '')}): {_money(c_ping)}"
            )
        lines.append(
            f"- Record interest rate: {estimation.get('record_interest_rate', '')}"
        )
        lines.append(
            f"- Account balance: {_money(estimation.get('account_balance'))} -> "
            f"stored: {_money(estimation.get('stored_balance'))}"
        )
        lines.append(
            f"- Monthly basic: {_money(estimation.get('monthly_basic_pension'))} | "
            f"account: {_money(estimation.get('monthly_account_pension'))} | "
            f"transition: {_money(estimation.get('monthly_transition_pension'))} | "
            f"total: {_money(estimation.get('monthly_total'))}"
        )
        assumptions = estimation.get("assumptions", [])
        if assumptions:
            lines.append("- Assumptions:")
            for assumption in assumptions:
                if isinstance(assumption, Mapping):
                    lines.append(
                        f"  - {assumption.get('name', '')}: {assumption.get('value', '')} "
                        f"({assumption.get('source_type', '')})"
                    )
        lines.append("")

    recommendation = output.get("recommendation")
    lines.append("## Recommendation")
    lines.append("")
    if isinstance(recommendation, Mapping):
        lines.append(f"- Recommended scenario: `{recommendation.get('scenario_id', '')}`")
        lines.append(f"- Objective: `{recommendation.get('objective', '')}`")
        limitations = recommendation.get("limitations", [])
        if limitations:
            lines.append("- Limitations:")
            for limitation in limitations:
                lines.append(f"  - {limitation}")
    else:
        lines.append("- No recommendation.")
    lines.append("")
    return "\n".join(lines)
