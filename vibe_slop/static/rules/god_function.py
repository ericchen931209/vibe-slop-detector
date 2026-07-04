"""S3 — God Function: functions that are too long or have too many parameters."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S3"
CATEGORY_NAME = "God Function"

_LINES_MEDIUM = 50
_LINES_HIGH = 100
_PARAMS_MEDIUM = 7


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []

    def walk(node: Node) -> None:
        if node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode() if name_node else "<anonymous>"
            start = node.start_point[0] + 1
            end = node.end_point[0] + 1
            length = end - start

            if length >= _LINES_HIGH:
                severity = Severity.HIGH
                detail = f'"{name}" is {length} lines long (threshold: {_LINES_HIGH})'
            elif length >= _LINES_MEDIUM:
                severity = Severity.MEDIUM
                detail = f'"{name}" is {length} lines long (threshold: {_LINES_MEDIUM})'
            else:
                severity = None

            if severity:
                findings.append(Finding(
                    category=CATEGORY,
                    category_name=CATEGORY_NAME,
                    severity=severity,
                    layer=Layer.STATIC,
                    line=start,
                    detail=detail,
                    snippet=lines[start - 1].strip() if start <= len(lines) else "",
                ))

            params = node.child_by_field_name("parameters")
            if params:
                param_count = sum(
                    1 for c in params.named_children
                    if c.type in ("identifier", "typed_parameter", "default_parameter",
                                  "typed_default_parameter", "list_splat_pattern",
                                  "dictionary_splat_pattern")
                )
                if param_count >= _PARAMS_MEDIUM:
                    findings.append(Finding(
                        category=CATEGORY,
                        category_name=CATEGORY_NAME,
                        severity=Severity.MEDIUM,
                        layer=Layer.STATIC,
                        line=start,
                        detail=f'"{name}" has {param_count} parameters (threshold: {_PARAMS_MEDIUM})',
                        snippet=lines[start - 1].strip() if start <= len(lines) else "",
                    ))

        for child in node.children:
            walk(child)

    walk(tree)
    return findings
