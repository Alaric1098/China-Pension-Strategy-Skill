"""Policy expiry report — maintenance-side data-freshness gate.

Scans `policy-data/packages` and reports packages *and rules* whose
validity (`effective_to`) has already lapsed or expires within the horizon.
Rule-level expiry matters because a rule version can end earlier than its
package (for example a source document's validity boundary). This is a
maintainer tool, deliberately OUTSIDE the user-facing skill surface: policy
expiry is data-governance, not a user question.

Historical packages (`historical: true` in the package record, for example
a deliberately archived past-period rate) are listed under HISTORICAL for
audit visibility but are NOT counted in the exit code: they are intentionally
expired and must not turn the maintenance gate red forever.

Usage:
    python scripts/policy_expiry_report.py [--horizon-months N] [--as-of YYYY-MM-DD]

Exit code: 0 when no *current* package or rule expires within the horizon;
1 when at least one non-historical package or rule is expired or expiring
soon (useful as a maintenance gate).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _months_between(as_of: date, end_date: date) -> int:
    return (end_date.year - as_of.year) * 12 + (end_date.month - as_of.month)


def _collect(path: Path) -> tuple[bool, list[dict], list[dict]]:
    """Return (is_historical, package-level entries, rule-level entries)."""
    package = json.loads(path.read_text(encoding="utf-8"))
    is_historical = bool(package.get("historical", False))
    package_entries: list[dict] = []
    rule_entries: list[dict] = []
    end = package.get("effective_to")
    if end:
        package_entries.append(
            {
                "level": "package",
                "package_id": package["package_id"],
                "rule_id": None,
                "jurisdiction": package.get("jurisdiction"),
                "topic": package.get("topic"),
                "effective_to": end,
            }
        )
    for rule in package.get("rules", ()):
        rule_end = rule.get("effective_to")
        if rule_end:
            rule_entries.append(
                {
                    "level": "rule",
                    "package_id": package["package_id"],
                    "rule_id": rule.get("rule_id"),
                    "jurisdiction": package.get("jurisdiction"),
                    "topic": rule.get("topic"),
                    "effective_to": rule_end,
                }
            )
    return is_historical, package_entries, rule_entries


def main() -> int:
    parser = argparse.ArgumentParser(prog="policy_expiry_report")
    parser.add_argument("--horizon-months", type=int, default=18)
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD reference date")
    parser.add_argument("--packages-dir", default=None, help="override packages directory")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    packages_dir = (
        Path(args.packages_dir) if args.packages_dir else ROOT / "policy-data" / "packages"
    )
    historical_entries: list[dict] = []
    current_entries: list[dict] = []
    for path in sorted(packages_dir.glob("*.json")):
        is_historical, package_entries, rule_entries = _collect(path)
        target = historical_entries if is_historical else current_entries
        for entry in package_entries + rule_entries:
            end_date = date.fromisoformat(entry["effective_to"])
            if end_date < as_of:
                target.append({**entry, "status": "EXPIRED"})
                continue
            months_left = _months_between(as_of, end_date)
            if months_left <= args.horizon_months:
                target.append({**entry, "status": "EXPIRING_SOON", "months_remaining": months_left})

    print(f"Policy expiry report (as of {as_of.isoformat()}, horizon {args.horizon_months} months)")
    if not current_entries and not historical_entries:
        print("  No packages or rules expire within the horizon.")
        return 0

    if historical_entries:
        print("  [HISTORICAL] (archived packages; not counted in the gate)")
        for entry in historical_entries:
            scope = entry["rule_id"] or "(package)"
            print(
                f"    {entry['package_id']} / {scope} "
                f"({entry['topic']}, {entry['jurisdiction']}) "
                f"effective_to {entry['effective_to']} [{entry['status']}]"
            )

    if current_entries:
        print("  [CURRENT] (non-historical; drives the gate)")
        for entry in current_entries:
            scope = entry["rule_id"] or "(package)"
            print(
                f"    [{entry['status']}] {entry['package_id']} / {scope} "
                f"({entry['topic']}, {entry['jurisdiction']}) "
                f"effective_to {entry['effective_to']}"
                + (
                    f", {entry['months_remaining']} months left"
                    if "months_remaining" in entry
                    else ""
                )
            )
    return 1 if current_entries else 0


if __name__ == "__main__":
    sys.exit(main())
