# vibe-slop

Detect AI-generated code anti-patterns ("vibe slop") in your codebase.

```
$ vibe-slop check myproject/
─────────────── vibe-slop · myproject/main.py ───────────────
  Sev    Line  Category              Detail
 ──────────────────────────────────────────────────────────── 
  HIGH   1     AI Signature Phrase   AI phrase detected: "Certainly"
  HIGH   23    False Safety Net      Exception handler silently swallows errors
  MEDIUM 8     Generic Naming        "result" used 4 times
  LOW    15    Void Abstraction      "get_name" is a single-line passthrough

Score: 72/100  Band: Very Sloppy
```

## Installation

```bash
pip install vibe-slop
```

Or from source:

```bash
git clone https://github.com/<your-username>/vibe-slop-detector
cd vibe-slop-detector
pip install -e .
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
