"""S3 — God Function: functions that are too long or have too many parameters."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S3"
CATEGORY_NAME = "God Function"

_LINES_MEDIUM = 50
_LINES_HIGH = 100
_PARAMS_MEDIUM = 7

_PARAM_TYPES = frozenset({
    "identifier", "typed_parameter", "default_parameter",
    "typed_default_parameter", "list_splat_pattern", "dictionary_splat_pattern",
})


def _snippet(lines: list[str], line: int) -> str:
    return lines[line - 1].strip() if line <= len(lines) else ""


def _check_length(name: str, start: int, length: int, lines: list[str]) -> Finding | None:
    if length >= _LINES_HIGH:
        severity, threshold = Severity.HIGH, _LINES_HIGH
    elif length >= _LINES_MEDIUM:
        severity, threshold = Severity.MEDIUM, _LINES_MEDIUM
    else:
        return None
    return Finding(
        category=CATEGORY, category_name=CATEGORY_NAME,
        severity=severity, layer=Layer.STATIC, line=start,
        detail=f'"{name}" is {length} lines long (threshold: {threshold})',
        snippet=_snippet(lines, start),
    )


def _check_params(name: str, start: int, params: Node, lines: list[str]) -> Finding | None:
    count = sum(1 for c in params.named_children if c.type in _PARAM_TYPES)
    if count < _PARAMS_MEDIUM:
        return None
    return Finding(
        category=CATEGORY, category_name=CATEGORY_NAME,
        severity=Severity.MEDIUM, layer=Layer.STATIC, line=start,
        detail=f'"{name}" has {count} parameters (threshold: {_PARAMS_MEDIUM})',
        snippet=_snippet(lines, start),
    )


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []

    def walk(node: Node) -> None:
        if node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode() if name_node else "<anonymous>"
            start = node.start_point[0] + 1
            length = node.end_point[0] + 1 - start

            if f := _check_length(name, start, length, lines):
                findings.append(f)

            params = node.child_by_field_name("parameters")
            if params and (f := _check_params(name, start, params, lines)):
                findings.append(f)

        for child in node.children:
            walk(child)

    walk(tree)
    return findings
