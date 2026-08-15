import json
import re
import sys
from pathlib import Path

from audit_architecture import structural_checks


ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def anchor(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff-]", "", value.strip().lower().replace(" ", "-"))


# Label words that are themselves field names, not values.
_LABEL = r"(?:校验码|查询流水号|社会保障号码)"

# Strong patterns stay strict: 18-digit IDs always match. Label patterns
# require a value-shaped suffix (alphanumerics/CJK, 4+ chars) AND forbid a
# second label word right after the colon, so bare field-name mentions
# (inside backticks or in odd-nesting residue) are not false positives.
SENSITIVE_PATTERN = re.compile(
    r"\b\d{17}[0-9Xx]\b"
    r"|" + _LABEL + r"[:：]\s*(?!" + _LABEL + r"[:：])[0-9A-Za-z\u4e00-\u9fff]{4,}"
)

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`{1,3}[^`\n]*?`{1,3}")


def strip_code_blocks(text: str) -> str:
    """Blank out fenced code blocks before sensitive scanning."""
    return _FENCE.sub(" ", text)


def scan_sensitive(text: str) -> list[str]:
    """Return every sensitive-identifier match (code spans excluded).

    Inline code spans (including odd-nesting backtick residue) are blanked
    iteratively; lone backticks left over from malformed nesting are also
    removed so a mention of a field *name* is documentation, not a leak.
    Writing an actual value outside code markup still matches.
    """
    cleaned = strip_code_blocks(text)
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = _INLINE.sub(" ", cleaned)
    cleaned = cleaned.replace("`", " ")
    return [match.group(0) for match in SENSITIVE_PATTERN.finditer(cleaned)]


def main() -> int:
    failures: list[str] = []
    markdown_files = [README, ROOT / "CHANGELOG.md", ROOT / "SKILL.md"]
    docs = ROOT / "docs"
    if docs.exists():
        markdown_files.extend(sorted(docs.rglob("*.md")))

    readme_text = README.read_text(encoding="utf-8")
    headings = {anchor(value) for value in re.findall(r"^## (.+)$", readme_text, re.M)}
    toc_links = re.findall(r"^- \[[^]]+\]\(#([^)]+)\)$", readme_text, re.M)
    missing_anchors = [value for value in toc_links if value not in headings]
    if missing_anchors:
        failures.append(f"README has missing anchors: {', '.join(missing_anchors)}")

    local_links = re.findall(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)", readme_text)
    for link in local_links:
        target = ROOT / link.split("#", 1)[0]
        if not target.exists():
            failures.append(f"README local link does not exist: {link}")

    for path in markdown_files:
        matches = scan_sensitive(path.read_text(encoding="utf-8"))
        if matches:
            failures.append(
                f"Sensitive identifier detected in {path.relative_to(ROOT)}: "
                f"{', '.join(sorted(set(matches))[:3])}"
            )

    if docs.exists():
        for path in docs.rglob("*.json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                failures.append(f"Invalid JSON in {path.relative_to(ROOT)}: {error}")

    for check in structural_checks():
        if not check["passed"]:
            failures.append(f"Design contract failed: {check['id']} ({check['description']})")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(
        f"PASS: {len(markdown_files)} Markdown files, {len(toc_links)} README TOC links, "
        f"{len(local_links)} local links, {len(structural_checks())} structural contracts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
