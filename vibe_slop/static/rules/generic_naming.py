"""S6 — Generic Naming: semantically empty variable/function/class names."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S6"
CATEGORY_NAME = "Generic Naming"

_GENERIC = frozenset({
    "data", "result", "results", "temp", "tmp", "info", "obj", "val", "value",
    "item", "items", "thing", "things", "stuff", "manager", "handler", "helper",
    "helpers", "utils", "util", "processor", "service", "controller", "response",
    "output", "input", "record", "records", "entry", "entries",
})

# Threshold: flag a file if a single generic name appears this many times
_COUNT_THRESHOLD = 4


def check(tree: Node, lines: list[str]) -> list[Finding]:
    counts: dict[str, list[int]] = {}

    def walk(node: Node) -> None:
        if node.type == "identifier":
            name = node.text.decode()
            if name in _GENERIC:
                line = node.start_point[0] + 1
                counts.setdefault(name, []).append(line)
        for child in node.children:
            walk(child)

    walk(tree)

    findings = []
    for name, occurrences in counts.items():
        if len(occurrences) >= _COUNT_THRESHOLD:
            findings.append(Finding(
                category=CATEGORY,
                category_name=CATEGORY_NAME,
                severity=Severity.MEDIUM,
                layer=Layer.STATIC,
                line=occurrences[0],
                detail=f'"{name}" used {len(occurrences)} times — consider a domain-specific name',
                suggestion=(
                    f'Rename "{name}" to reflect what it actually holds. '
                    f'Examples: "data" → "user_records" / "api_response"; '
                    f'"result" → "parsed_config" / "matched_products".'
                ),
            ))
    return findings
