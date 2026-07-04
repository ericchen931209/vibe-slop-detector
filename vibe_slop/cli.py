"""CLI entry point: vibe-slop check <file|dir> [options]"""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from vibe_slop.analyzer import analyze
from vibe_slop.report import human as human_report
from vibe_slop.report import machine as machine_report

app = typer.Typer(name="vibe-slop", add_completion=False, no_args_is_help=True, help="Detect AI-generated code anti-patterns.")
console = Console(stderr=True)

_SUPPORTED = {".py"}  # expand in future versions


def _collect_files(target: Path, ignore: list[str]) -> list[Path]:
    import fnmatch
    if target.is_file():
        return [target]

    files = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in _SUPPORTED:
            continue
        rel = str(path.relative_to(target))
        if any(fnmatch.fnmatch(rel, pat) for pat in ignore):
            continue
        files.append(path)
    return files


@app.command()
def check(
    target: Path = typer.Argument(..., help="File or directory to analyze"),
    llm: bool = typer.Option(False, "--llm", help="Enable LLM semantic analysis (requires ANTHROPIC_API_KEY)"),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
    ignore: Optional[str] = typer.Option(None, "--ignore", help='Glob patterns to ignore, comma-separated (e.g. "models/*,*_pb2.py")'),
    min_severity: str = typer.Option("LOW", "--min-severity", help="Minimum severity to show: HIGH, MEDIUM, LOW"),
) -> None:
    """Analyze a file or directory for vibe slop patterns."""
    if not target.exists():
        console.print(f"[red]Error:[/red] path not found: {target}")
        raise typer.Exit(1)

    ignore_patterns = [p.strip() for p in ignore.split(",")] if ignore else []
    files = _collect_files(target, ignore_patterns)

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(0)

    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    min_sev_rank = severity_order.get(min_severity.upper(), 2)

    exit_code = 0
    for path in files:
        report = analyze(path, use_llm=llm)

        # Filter findings by severity
        report.findings = [
            f for f in report.findings
            if severity_order.get(f.severity.value, 2) <= min_sev_rank
        ]

        if report.findings or report.error:
            exit_code = 1

        if json_output:
            machine_report.print_json(report)
        else:
            human_report.print_report(report)

    raise typer.Exit(exit_code)


@app.command()
def rules() -> None:
    """List all slop categories in the taxonomy."""
    from rich.table import Table
    from rich import box
    from rich.console import Console

    _console = Console()
    table = Table(box=box.SIMPLE_HEAD, header_style="bold", show_header=True)
    table.add_column("ID", width=5)
    table.add_column("Name", width=24)
    table.add_column("Layer", width=12)
    table.add_column("Severity", width=8)
    table.add_column("Description")

    _RULES = [
        ("S1",  "Ghost Comment",          "LLM",        "MEDIUM", "Comment restates what code obviously does"),
        ("S2",  "AI Signature Phrase",    "Static",     "HIGH",   "AI assistant phrases in comments/docstrings"),
        ("S3",  "God Function",           "Static",     "HIGH",   "Function too long or too many parameters"),
        ("S4",  "Dead Import",            "Static",     "LOW",    "Imported module never used"),
        ("S5",  "Copy-Paste Clone",       "Static",     "HIGH",   "Near-identical duplicated code blocks"),
        ("S6",  "Generic Naming",         "Static+LLM", "MEDIUM", "Semantically empty names like 'data', 'result'"),
        ("S7",  "Void Abstraction",       "Static",     "LOW",    "Single-line passthrough function"),
        ("S8",  "Magic Number",           "Static",     "MEDIUM", "Unnamed numeric literal in logic"),
        ("S9",  "False Safety Net",       "Static",     "HIGH",   "Exception handler that swallows errors silently"),
        ("S10", "Verbosity Inflation",    "LLM",        "MEDIUM", "Far more lines than the task requires"),
        ("S11", "Redundant Docstring",    "LLM",        "LOW",    "Docstring that restates the function name"),
        ("S12", "Defensive Over-check",   "Static+LLM", "LOW",    "Guards for impossible conditions"),
        ("S13", "TODO Graveyard",         "Static",     "LOW",    "Excessive TODO/FIXME markers"),
    ]

    for row in _RULES:
        table.add_row(*row)

    _console.print(table)


if __name__ == "__main__":
    app()
