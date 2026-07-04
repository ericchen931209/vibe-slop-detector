"""S8 — Magic Number: unnamed numeric literals in logic."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S8"
CATEGORY_NAME = "Magic Number"

_ALLOWED = {0, 1, -1, 2, 100}  # common and usually self-evident


def _in_assignment_value(node: Node) -> bool:
    """True if this node is the right-hand side of a simple assignment (constant definition)."""
    parent = node.parent
    if parent and parent.type == "assignment":
        value_field = parent.child_by_field_name("right")
        if value_field and value_field == node:
            # Left side should be a plain UPPER_CASE identifier (convention for constants)
            left = parent.child_by_field_name("left")
            if left and left.type == "identifier":
                name = left.text.decode()
                if name.isupper():
                    return True
    return False


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings = []

    def walk(node: Node) -> None:
        if node.type == "integer" or node.type == "float":
            try:
                numeric = float(node.text.decode())
            except ValueError:
                numeric = None

            if numeric is not None and numeric not in _ALLOWED and not _in_assignment_value(node):
                parent = node.parent
                # Only flag numbers that appear in conditions, slices, arithmetic
                if parent and parent.type in (
                    "comparison_operator", "binary_operator", "augmented_assignment",
                    "slice", "argument_list", "call", "return_statement",
                ):
                    line = node.start_point[0] + 1
                    findings.append(Finding(
                        category=CATEGORY,
                        category_name=CATEGORY_NAME,
                        severity=Severity.MEDIUM,
                        layer=Layer.STATIC,
                        line=line,
                        detail=f"Magic number {node.text.decode()} — consider naming it as a constant",
                        snippet=lines[line - 1].strip() if line <= len(lines) else "",
                    ))

        for child in node.children:
            walk(child)

    walk(tree)
    return findings
