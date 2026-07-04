"""S4 — Dead Import: modules imported but never referenced."""
from tree_sitter import Node

from vibe_slop.models import Finding, Layer, Severity

CATEGORY = "S4"
CATEGORY_NAME = "Dead Import"


def _collect_imports(node: Node) -> list[tuple[str, int]]:
    """Return list of (name, line) for all imported names."""
    imports = []
    if node.type in ("import_statement", "import_from_statement"):
        line = node.start_point[0] + 1
        for child in node.named_children:
            if child.type == "dotted_name":
                imports.append((child.text.decode(), line))
            elif child.type == "aliased_import":
                alias = child.child_by_field_name("alias")
                name = child.child_by_field_name("name")
                token = alias or name
                if token:
                    imports.append((token.text.decode(), line))
            elif child.type == "identifier":
                imports.append((child.text.decode(), line))
    for child in node.children:
        imports.extend(_collect_imports(child))
    return imports


def _collect_identifiers(node: Node, skip_types: set[str]) -> set[str]:
    """Return all identifier texts outside import statements."""
    names = set()
    if node.type in skip_types:
        return names
    if node.type == "identifier":
        names.add(node.text.decode())
    for child in node.children:
        names |= _collect_identifiers(child, skip_types)
    return names


def check(tree: Node, lines: list[str]) -> list[Finding]:
    import_nodes = {"import_statement", "import_from_statement"}
    all_imports = _collect_imports(tree)
    if not all_imports:
        return []

    used_names = _collect_identifiers(tree, skip_types=import_nodes)

    findings = []
    seen = set()
    for name, line in all_imports:
        # Deduplicate and skip __future__ imports
        if name in seen or name == "__future__":
            continue
        seen.add(name)
        if name not in used_names:
            findings.append(Finding(
                category=CATEGORY,
                category_name=CATEGORY_NAME,
                severity=Severity.LOW,
                layer=Layer.STATIC,
                line=line,
                detail=f'"{name}" is imported but never used',
                snippet=lines[line - 1].strip() if line <= len(lines) else "",
            ))
    return findings
