# vibe-slop

Find slop patterns in your code and get concrete fix suggestions.

"Vibe slop" refers to low-quality, redundant, or low-signal code patterns — \
common in AI-assisted coding but found anywhere — that hurt readability and maintainability.

```
$ vibe-slop check myproject/main.py
─────────────── vibe-slop · myproject/main.py ───────────────
  Sev    Line  Category              Detail
 ────────────────────────────────────────────────────────────
  HIGH   1     AI Signature Phrase   AI phrase detected: "Certainly"
  HIGH   23    False Safety Net      Exception handler silently swallows errors
  MEDIUM 8     Generic Naming        "result" used 4 times
  LOW    15    Void Abstraction      "get_name" is a single-line passthrough

Score: 72/100  Band: Very Sloppy

Fix suggestions:
╭─ HIGH False Safety Net (line 23) ─────────────────────────────╮
│ Catch a specific exception type and handle it meaningfully:   │
│ log with context, return a safe default, or re-raise.         │
╰───────────────────────────────────────────────────────────────╯
╭─ MEDIUM Generic Naming (line 8) ──────────────────────────────╮
│ Rename "result" to reflect what it holds.                     │
│ Example: "result" → "matched_products" / "parsed_config"      │
╰───────────────────────────────────────────────────────────────╯
```

## Installation

**Recommended (installs as a standalone CLI tool):**

```bash
pipx install git+https://github.com/ericchen931209/vibe-slop-detector.git
```

If you don't have `pipx`:

```bash
# macOS
brew install pipx

# Ubuntu / Debian
sudo apt install pipx && pipx ensurepath
```

**Or in a virtual environment:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/ericchen931209/vibe-slop-detector.git
```

**Or from source (for development):**

```bash
git clone https://github.com/ericchen931209/vibe-slop-detector
cd vibe-slop-detector
pip install -e ".[dev]"
```

## Usage

```bash
# Check a single file
vibe-slop check main.py

# Check a whole directory
vibe-slop check src/

# Ignore boilerplate paths
vibe-slop check src/ --ignore "models/*,*_pb2.py,migrations/*"

# Only show HIGH and MEDIUM severity
vibe-slop check src/ --min-severity MEDIUM

# Machine-readable JSON output (for CI or AI consumption)
vibe-slop check src/ --json

# Enable LLM semantic analysis (requires ANTHROPIC_API_KEY)
vibe-slop check src/ --llm

# List all detection rules
vibe-slop rules
```

## What it detects

| ID | Name | Severity | Description |
|---|---|---|---|
| S1 | Ghost Comment | MEDIUM | Comment restates what code obviously does |
| S2 | AI Signature Phrase | HIGH | AI assistant phrases in comments ("certainly", "of course") |
| S3 | God Function | HIGH | Function too long (>50 lines) or too many parameters (>7) |
| S4 | Dead Import | LOW | Imported module never used |
| S5 | Copy-Paste Clone | HIGH | Near-identical duplicated code blocks |
| S6 | Generic Naming | MEDIUM | Semantically empty names like `data`, `result`, `temp` |
| S7 | Void Abstraction | LOW | Single-line passthrough function with no added value |
| S8 | Magic Number | MEDIUM | Unnamed numeric literal in logic |
| S9 | False Safety Net | HIGH | `except: pass` or exception handler that swallows errors |
| S10 | Verbosity Inflation | MEDIUM | Far more lines than the task requires |
| S11 | Redundant Docstring | LOW | Docstring that merely restates the function name |
| S12 | Defensive Over-check | LOW | Guards for impossible conditions (`if x is not None and x != None`) |
| S13 | TODO Graveyard | LOW | Excessive TODO/FIXME markers left in code |

See [TAXONOMY.md](TAXONOMY.md) for full specification.

## Slop Score

Each file receives a score from 0–100:

| Score | Band |
|---|---|
| 0–20 | Clean |
| 21–40 | Slightly Sloppy |
| 41–60 | Sloppy |
| 61–80 | Very Sloppy |
| 81–100 | Slop |

## Detection layers

- **Static** — Fast, deterministic AST analysis via [tree-sitter](https://github.com/tree-sitter/tree-sitter). No network required.
- **LLM** — Semantic analysis via Claude API (opt-in with `--llm`). Catches intent-level slop that static analysis misses.

## Suppressing false positives

Add `# noqa: S7` to suppress Void Abstraction on intentional delegation:

```python
def send_email(address, content):  # noqa: S7
    return email_service.send(address, content)
```

## Supported languages

| Version | Languages |
|---|---|
| v0.1 | Python |
| v0.2 (planned) | JavaScript, TypeScript |
| v0.3 (planned) | Java, Go |

## License

MIT
