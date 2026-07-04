"""S9 — False Safety Net: exception handlers that swallow errors silently."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S9"
CATEGORY_NAME = "False Safety Net"


def _is_silent_body(body: Node) -> bool:
    """True if except body contains only pass, print, or logging calls."""
    stmts = [c for c in body.named_children if c.type not in ("comment",)]
    if not stmts:
        return True
    if len(stmts) == 1:
        s = stmts[0]
        if s.type == "pass_statement":
            return True
        if s.type == "expression_statement":
            expr = s.named_children[0] if s.named_children else None
            if expr and expr.type == "call":
                func = expr.child_by_field_name("function")
                if func and func.text.decode() in ("print", "logging.error",
                                                    "logging.warning", "logging.info",
                                                    "logging.debug", "logger.error",
                                                    "logger.warning", "logger.info"):
                    return True
    return False


def _walk(node: Node, findings: list[Finding], lines: list[str]) -> None:
    if node.type == "try_statement":
        for child in node.named_children:
            if child.type == "except_clause":
                line = child.start_point[0] + 1
                body = child.child_by_field_name("body") or (
                    child.named_children[-1] if child.named_children else None
                )
                # Bare except (no exception type specified)
                has_type = any(c.type not in ("body", "block", "comment", "as_pattern")
                               and c.type != "except"
                               for c in child.named_children
                               if c.type not in ("block",))

                if body and _is_silent_body(body):
                    findings.append(Finding(
                        category=CATEGORY,
                        category_name=CATEGORY_NAME,
                        severity=Severity.HIGH,
                        layer=Layer.STATIC,
                        line=line,
                        detail="Exception handler silently swallows errors (no re-raise)",
                        suggestion=(
                            "Catch a specific exception type and handle it meaningfully: "
                            "log with context, return a safe default, or re-raise. "
                            "Example: `except ValueError as e: logger.warning('...', exc_info=e); raise`"
                        ),
                        snippet=lines[line - 1].strip() if line <= len(lines) else "",
                    ))
    for child in node.children:
        _walk(child, findings, lines)


def check(tree: Node, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    _walk(tree, findings, lines)
    return findings
