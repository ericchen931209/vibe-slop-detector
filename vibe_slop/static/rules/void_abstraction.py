"""S7 — Void Abstraction: single-expression wrapper functions with no added value.

Default ON at LOW severity. May produce false positives for intentional delegation
patterns — user can suppress with inline comment: # noqa: S7
"""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S7"
CATEGORY_NAME = "Void Abstraction"


def _is_single_return_passthrough(func_node: Node) -> bool:
    """True if function body is exactly one return of an attribute access or call."""
    body = func_node.child_by_field_name("body")
    if not body:
        return False

    stmts = [c for c in body.named_children if c.type != "comment"]
    if len(stmts) != 1:
        return False

    stmt = stmts[0]
    if stmt.type != "return_statement":
        return False

    value = stmt.named_children[0] if stmt.named_children else None
    if value is None:
        return False

    return value.type in ("attribute", "call", "identifier")


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []

    def walk(node: Node) -> None:
        if node.type in ("function_definition", "async_function_definition"):
            line = node.start_point[0] + 1
            raw_line = lines[line - 1] if line <= len(lines) else ""

            # Respect suppression comment
            if "# noqa: S7" in raw_line:
                for child in node.children:
                    walk(child)
                return

            if _is_single_return_passthrough(node):
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode() if name_node else "<anonymous>"
                findings.append(Finding(
                    category=CATEGORY,
                    category_name=CATEGORY_NAME,
                    severity=Severity.LOW,
                    layer=Layer.STATIC,
                    line=line,
                    detail=f'"{name}" is a single-line passthrough — may be a void abstraction',
                    snippet=raw_line.strip(),
                ))

        for child in node.children:
            walk(child)

    walk(tree)
    return findings
