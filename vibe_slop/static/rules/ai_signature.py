"""S2 — AI Signature Phrase: AI assistant phrases leaked into comments/docstrings."""
import re
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

_PHRASES = re.compile(
    r"\b(certainly|of course|as an ai|i'd be happy|i cannot|i'm sorry|sure!|"
    r"i hope this helps|feel free to|don't hesitate)\b",
    re.IGNORECASE,
)

CATEGORY = "S2"
CATEGORY_NAME = "AI Signature Phrase"


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not (stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")):
            # Only check comment and docstring lines (fast pre-filter)
            # Full docstring body lines don't start with quotes, so also scan those
            # if they're inside a string — tree-sitter handles this precisely but
            # regex on raw text is enough for these distinctive phrases.
            pass
        match = _PHRASES.search(line)
        if match:
            findings.append(Finding(
                category=CATEGORY,
                category_name=CATEGORY_NAME,
                severity=Severity.HIGH,
                layer=Layer.STATIC,
                line=i,
                detail=f'AI phrase detected: "{match.group()}"',
                snippet=line.strip(),
            ))
    return findings
