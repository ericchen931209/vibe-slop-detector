from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from vibe_slop.models import Finding
from vibe_slop.static.rules import (
    ai_signature,
    dead_import,
    false_safety_net,
    generic_naming,
    god_function,
    magic_number,
    todo_graveyard,
    void_abstraction,
)

PY_LANGUAGE = Language(tspython.language())

PYTHON_RULES = [
    ai_signature.check,
    dead_import.check,
    false_safety_net.check,
    generic_naming.check,
    god_function.check,
    magic_number.check,
    todo_graveyard.check,
    void_abstraction.check,
]


def parse_python(source: bytes) -> Node:
    parser = Parser(PY_LANGUAGE)
    return parser.parse(source).root_node


def analyze_file(path: Path) -> list[Finding]:
    source = path.read_bytes()
    tree = parse_python(source)
    source_lines = source.decode("utf-8", errors="replace").splitlines()

    findings: list[Finding] = []
    for rule in PYTHON_RULES:
        findings.extend(rule(tree, source_lines))

    return findings
