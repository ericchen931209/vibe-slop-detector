"""Machine-readable JSON report."""
import json
from vibe_slop.models import FileReport


def to_dict(report: FileReport) -> dict:
    return {
        "file": str(report.path),
        "score": report.score,
        "band": report.band,
        "error": report.error or None,
        "findings": [
            {
                "category": f.category,
                "category_name": f.category_name,
                "severity": f.severity.value,
                "layer": f.layer.value,
                "line": f.line,
                "detail": f.detail,
                "suggestion": f.suggestion,
                "snippet": f.snippet,
            }
            for f in sorted(report.findings, key=lambda x: x.line)
        ],
    }


def print_json(report: FileReport) -> None:
    print(json.dumps(to_dict(report), indent=2, ensure_ascii=False))
