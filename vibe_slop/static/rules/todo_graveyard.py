"""S13 — TODO Graveyard: excessive TODO/FIXME/HACK markers left in code."""
import re
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S13"
CATEGORY_NAME = "TODO Graveyard"

# Only match markers inside comments (after #), not in strings or docstrings
_MARKER = re.compile(r"#[^#\n]*\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
_THRESHOLD_MEDIUM = 3
_THRESHOLD_HIGH = 7


def check(tree: Node, lines: list[str]) -> list[Finding]:
    hits: list[int] = []
    for i, line in enumerate(lines, start=1):
        if _MARKER.search(line):
            hits.append(i)

    if len(hits) < _THRESHOLD_MEDIUM:
        return []

    severity = Severity.HIGH if len(hits) >= _THRESHOLD_HIGH else Severity.MEDIUM
    return [Finding(
        category=CATEGORY,
        category_name=CATEGORY_NAME,
        severity=severity,
        layer=Layer.STATIC,
        line=hits[0],
        detail=f"{len(hits)} TODO/FIXME markers found (first at line {hits[0]})",
        suggestion=(
            "For each TODO: either implement it now, file a GitHub issue with the details "
            "and replace the comment with the issue URL, or delete it if it's no longer relevant."
        ),
    )]
