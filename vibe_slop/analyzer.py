"""Orchestrate static + LLM analysis and produce a FileReport."""
from pathlib import Path

from vibe_slop.models import FileReport
from vibe_slop.static import engine as static_engine


def analyze(path: Path, use_llm: bool = False) -> FileReport:
    report = FileReport(path=path)

    try:
        source = path.read_text(errors="replace")
    except OSError as e:
        report.error = str(e)
        return report

    total_lines = len(source.splitlines())

    try:
        report.findings.extend(static_engine.analyze_file(path))
    except Exception as e:
        report.error = f"Static analysis failed: {e}"
        return report

    if use_llm:
        try:
            from vibe_slop.llm import judge
            report.findings.extend(judge.analyze_file(path))
        except Exception as e:
            # LLM failure is non-fatal; report what we have
            report.findings  # keep static results
            report.error = f"LLM analysis failed (static results shown): {e}"

    report.compute_score(total_lines)
    return report
