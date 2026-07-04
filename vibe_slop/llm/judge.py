"""LLM Judge: uses Claude API to detect semantic slop (S1, S10, S11)."""
from pathlib import Path

import anthropic

from vibe_slop.models import Finding, Layer, Severity

CATEGORY_MAP = {
    "S1":  ("Ghost Comment",       Severity.MEDIUM),
    "S10": ("Verbosity Inflation", Severity.MEDIUM),
    "S11": ("Redundant Docstring", Severity.LOW),
}

_SYSTEM = """\
You are a code quality analyzer specializing in detecting AI-generated code anti-patterns ("vibe slop").
Analyze the provided code and return findings as a JSON array.

Each finding must have these fields:
- "category": one of "S1", "S10", "S11"
- "line": integer (1-indexed line number where the issue starts)
- "detail": string explaining the specific problem (1-2 sentences, concrete)

Categories:
- S1 Ghost Comment: a comment that restates what the adjacent code obviously does, adding zero information
- S10 Verbosity Inflation: code that accomplishes a simple task in far more lines than necessary
- S11 Redundant Docstring: docstring that merely restates the function name or signature

Return ONLY a valid JSON array. Empty array if no findings. No markdown, no explanation outside the array.
Example: [{"category": "S1", "line": 12, "detail": "Comment 'increment counter' restates the obvious operation counter += 1"}]
"""


def analyze_file(path: Path) -> list[Finding]:
    source = path.read_text(errors="replace")
    if not source.strip():
        return []

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"File: {path.name}\n\n```python\n{source}\n```"}],
    )

    import json
    try:
        raw = message.content[0].text.strip()
        items = json.loads(raw)
    except (json.JSONDecodeError, IndexError, KeyError):
        return []

    lines = source.splitlines()
    findings = []
    for finding_data in items:
        cat = finding_data.get("category", "")
        if cat not in CATEGORY_MAP:
            continue
        name, severity = CATEGORY_MAP[cat]
        line = int(finding_data.get("line", 0))
        findings.append(Finding(
            category=cat,
            category_name=name,
            severity=severity,
            layer=Layer.LLM,
            line=line,
            detail=finding_data.get("detail", ""),
            snippet=lines[line - 1].strip() if 0 < line <= len(lines) else "",
        ))
    return findings
