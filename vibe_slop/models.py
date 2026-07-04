from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Layer(str, Enum):
    STATIC = "static"
    LLM = "llm"


SEVERITY_WEIGHT = {
    Severity.HIGH: 10,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
}

SCORE_BANDS = [
    (20, "Clean"),
    (40, "Slightly Sloppy"),
    (60, "Sloppy"),
    (80, "Very Sloppy"),
    (100, "Slop"),
]


@dataclass
class Finding:
    category: str          # e.g. "S3", "god_function"
    category_name: str     # human-readable name
    severity: Severity
    layer: Layer
    line: int              # 1-indexed; 0 means file-level
    detail: str            # explanation of this specific finding
    suggestion: str = ""   # concrete fix suggestion
    snippet: str = ""      # relevant code snippet (optional)


@dataclass
class FileReport:
    path: Path
    findings: list[Finding] = field(default_factory=list)
    score: int = 0
    band: str = "Clean"
    error: str = ""        # non-empty if file could not be analyzed

    def compute_score(self, total_lines: int) -> None:
        if not self.findings or total_lines == 0:
            self.score = 0
            self.band = "Clean"
            return

        SCORE_SCALE = 10
        raw = sum(SEVERITY_WEIGHT[f.severity] for f in self.findings)
        normalizer = max(total_lines / 100, 1)
        self.score = min(100, round(raw / normalizer * SCORE_SCALE))

        for threshold, label in SCORE_BANDS:
            if self.score <= threshold:
                self.band = label
                return
