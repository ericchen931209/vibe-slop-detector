"""S2 — AI Signature Phrase: AI assistant phrases leaked into comments/docstrings."""
import re
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

# Only match phrases when they appear inside a comment (after #)
_COMMENT_PHRASE = re.compile(
    r"#[^#\n]*\b(certainly|of course|as an ai|i'?d be happy|i cannot|i'?m sorry|sure!|"
    r"i hope this helps|feel free to|don't hesitate)\b",
    re.IGNORECASE,
)

CATEGORY = "S2"
CATEGORY_NAME = "AI Signature Phrase"


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []
    for i, line in enumerate(lines, start=1):
        # Only scan lines where # is the first non-whitespace character (pure comment)
        if not line.lstrip().startswith("#"):
            continue
        match = _COMMENT_PHRASE.search(line)
        if match:
            phrase = next(g for g in match.groups() if g)
            findings.append(Finding(
                category=CATEGORY,
                category_name=CATEGORY_NAME,
                severity=Severity.HIGH,
                layer=Layer.STATIC,
                line=i,
                detail=f'AI phrase detected: "{phrase}"',
                suggestion="Remove or rewrite the comment without AI assistant phrasing.",
                snippet=line.strip(),
            ))
    return findings
