"""Human-readable terminal report using rich."""
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.panel import Panel

from vibe_slop.models import FileReport, Severity

console = Console()

_SEVERITY_COLOR = {
    Severity.HIGH:   "bold red",
    Severity.MEDIUM: "yellow",
    Severity.LOW:    "dim cyan",
}

_BAND_COLOR = {
    "Clean":           "bold green",
    "Slightly Sloppy": "green",
    "Sloppy":          "yellow",
    "Very Sloppy":     "bold red",
    "Slop":            "bold red on white",
}


def print_report(report: FileReport) -> None:
    console.rule(f"[bold]vibe-slop[/bold] · {report.path}")

    if report.error:
        console.print(f"[red]Error:[/red] {report.error}")
        return

    if not report.findings:
        console.print("[bold green]✓ No slop detected[/bold green]")
        _print_score(report)
        return

    # Summary table
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    table.add_column("Sev", style="bold", width=6)
    table.add_column("Line", width=6)
    table.add_column("Category", width=22)
    table.add_column("Detail")

    sorted_findings = sorted(report.findings, key=lambda x: (x.line, x.severity))
    for f in sorted_findings:
        sev_text = Text(f.severity.value, style=_SEVERITY_COLOR[f.severity])
        line_str = str(f.line) if f.line > 0 else "—"
        table.add_row(sev_text, line_str, f.category_name, f.detail)

    console.print(table)
    _print_score(report)

    # Fix suggestions (only show findings that have suggestions)
    with_suggestions = [f for f in sorted_findings if f.suggestion]
    if not with_suggestions:
        return

    console.print("[bold]Fix suggestions:[/bold]")
    for f in with_suggestions:
        sev_color = _SEVERITY_COLOR[f.severity]
        line_str = f"line {f.line}" if f.line > 0 else "file"
        header = f"[{sev_color}]{f.severity.value}[/{sev_color}] {f.category_name} ({line_str})"
        console.print(Panel(
            f.suggestion,
            title=header,
            title_align="left",
            border_style="dim",
            padding=(0, 1),
        ))
    console.print()


def _print_score(report: FileReport) -> None:
    color = _BAND_COLOR.get(report.band, "white")
    console.print(
        f"\nScore: [bold]{report.score}[/bold]/100  "
        f"Band: [{color}]{report.band}[/{color}]\n"
    )
