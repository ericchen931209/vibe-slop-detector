# Vibe Slop Taxonomy v1.0

> A formal classification of AI-generated code anti-patterns ("vibe slop").
> This taxonomy serves as the detection spec for the vibe-slop-detector tool.

---

## Severity Levels

| Level | Description |
|---|---|
| `HIGH` | Strongly indicates AI-generated slop, or significantly hurts readability/maintainability |
| `MEDIUM` | Common slop pattern, context-dependent |
| `LOW` | Minor signal, worth noting but not alarming |

---

## Detection Layers

- **Static** — Detected via AST analysis (tree-sitter). Fast, deterministic, language-aware.
- **LLM** — Detected via Claude API judge. Handles semantics and intent.
- **Static+LLM** — Static finds candidates; LLM confirms and explains.

---

## Category Reference

### S1 — Ghost Comment
**Layer:** LLM
**Severity:** MEDIUM

A comment that restates what the code obviously does, adding no information.

```python
# Bad (ghost comment)
counter = counter + 1  # increment counter by 1
return result          # return the result

# Good
counter += 1
return result
```

**Detection signal:** Comment content maps 1:1 to the expression on the same or adjacent line.

---

### S2 — AI Signature Phrase
**Layer:** Static
**Severity:** HIGH

AI assistant phrases that leaked into comments, docstrings, or string literals.

```python
# Bad
# Certainly! Here's the implementation:
# As an AI language model, I cannot...
# Of course, I'd be happy to help with that.

# Bad (docstring)
def solve():
    """
    Sure! This function solves the problem by...
    """
```

**Detection signal:** Regex match on phrases: `certainly`, `of course`, `as an ai`, `i'd be happy`, `i cannot`, `i'm sorry`, `sure!`.

---

### S3 — God Function
**Layer:** Static
**Severity:** HIGH

A single function doing too many things — a common AI pattern of dumping all logic into one block.

```python
# Bad
def process_user_data(user_id):
    # fetch user
    # validate input
    # transform data
    # write to database
    # send email
    # log everything
    # ... 120 lines
```

**Thresholds (configurable):**
- Lines > 50: MEDIUM
- Lines > 100: HIGH
- Parameters > 7: MEDIUM

**Detection signal:** Function body line count; parameter count.

---

### S4 — Dead Import
**Layer:** Static
**Severity:** LOW

Modules imported but never referenced in the file.

```python
# Bad
import json        # never used
import threading   # never used
from typing import Optional  # used nowhere
```

**Detection signal:** AST import nodes vs. name reference nodes in the same file.

---

### S5 — Copy-Paste Clone
**Layer:** Static
**Severity:** HIGH

Near-identical code blocks duplicated within the same file. AI frequently generates repetitive code without noticing similarity.

```python
# Bad
def validate_email(email):
    if not email:
        return False
    if "@" not in email:
        return False
    return True

def check_email(e):
    if not e:
        return False
    if "@" not in e:
        return False
    return True
```

**Detection signal:** Token-level similarity > 80% between two function bodies in the same file.

---

### S6 — Generic Naming
**Layer:** Static+LLM
**Severity:** MEDIUM

Overuse of semantically empty names. AI tends to default to these when it lacks domain context.

**Flagged identifiers (variables, functions, classes):**
`data`, `result`, `temp`, `tmp`, `info`, `obj`, `val`, `value`, `item`, `thing`,
`manager`, `handler`, `helper`, `utils`, `util`, `processor`, `service`, `controller`

```python
# Bad
def process(data):
    result = []
    for item in data:
        temp = item.get("value")
        result.append(temp)
    return result

# Good
def extract_prices(products):
    return [p.get("price") for p in products]
```

**Detection signal:** Static counts occurrences per file; LLM judges whether domain-specific names were available.

---

### S7 — Void Abstraction
**Layer:** Static
**Severity:** LOW

A function whose entire body is a single expression or pass-through call, providing no additional abstraction value.

```python
# Bad
def get_user_name(user):
    return user.name

def is_valid(x):
    return validate(x)
```

**Exception:** Single-line functions with meaningful type coercion, adapter pattern, or documented interface contract are acceptable.

**Detection signal:** Function body has exactly 1 statement, which is a return of a single attribute access or function call.

---

### S8 — Magic Number
**Layer:** Static
**Severity:** MEDIUM

Numeric literals used directly in logic without a named constant, making intent unclear.

```python
# Bad
if response.status == 200:
    ...
if len(data) > 1000:
    ...
time.sleep(3)

# Good
HTTP_OK = 200
MAX_BATCH_SIZE = 1000
RETRY_DELAY_SECONDS = 3
```

**Exceptions:** `0`, `1`, `-1` are generally acceptable. `2` is context-dependent.

**Detection signal:** Numeric literal in conditional, slice, or arithmetic that is not `0`, `1`, or `-1`.

---

### S9 — False Safety Net
**Layer:** Static
**Severity:** HIGH

Exception handling that silently swallows errors — a common AI pattern to "handle" errors without understanding them.

```python
# Bad — silent swallow
try:
    risky_operation()
except:
    pass

# Bad — print-and-ignore
try:
    risky_operation()
except Exception as e:
    print(e)

# Bad — bare except
try:
    risky_operation()
except Exception:
    pass
```

**Detection signal:**
- `except` block with only `pass`
- `except` block with only `print()`/`logging` and no re-raise
- Bare `except:` (catches BaseException)

---

### S10 — Verbosity Inflation
**Layer:** LLM
**Severity:** MEDIUM

Code that accomplishes a simple task in far more lines than necessary, often via unnecessary intermediate variables or exploded logic.

```python
# Bad
def is_even(n):
    remainder = n % 2
    if remainder == 0:
        return True
    else:
        return False

# Good
def is_even(n):
    return n % 2 == 0
```

**Detection signal:** LLM evaluates if the function can be expressed more concisely without loss of clarity.

---

### S11 — Redundant Docstring
**Layer:** LLM
**Severity:** LOW

A docstring that merely restates the function name or signature, contributing no understanding.

```python
# Bad
def add(a, b):
    """Add a and b and return the result."""
    return a + b

def get_user(user_id):
    """Get the user by user_id."""
    ...

# Good
def add(a, b):
    """Compute element-wise addition. Wraps numpy.add for type-safe inputs."""
    ...
```

**Detection signal:** LLM measures semantic overlap between docstring and function signature.

---

### S12 — Defensive Over-checking
**Layer:** Static+LLM
**Severity:** LOW

Redundant guards and conditions that check for states that cannot occur given the code's control flow.

```python
# Bad
if x is not None and x != None:   # x != None is redundant
    ...

if len(arr) > 0:    # use truthiness: `if arr:`
    ...

if result == True:  # use truthiness: `if result:`
    ...
```

**Detection signal:** Static detects `!= None`, `== True`, `== False`, `len(x) > 0`; LLM detects logically impossible branches.

---

### S13 — TODO Graveyard
**Layer:** Static
**Severity:** LOW

Excessive TODO/FIXME/HACK comments left in production code, often placed by AI as placeholders it never fills in.

```python
# TODO: add error handling
# TODO: validate input
# FIXME: this might break on edge cases
# HACK: temporary workaround
```

**Threshold:** 3+ TODO/FIXME comments in a single file = LOW; 7+ = MEDIUM.

**Detection signal:** Regex count of `TODO`, `FIXME`, `HACK`, `XXX` comment markers.

---

## Scoring

Each file receives a **Slop Score** from 0–100 (lower = cleaner):

```
score = Σ (finding_weight × severity_multiplier) / normalizer
```

| Severity | Weight |
|---|---|
| HIGH | 10 |
| MEDIUM | 5 |
| LOW | 2 |

Normalizer is based on file length (per 100 lines) to avoid penalizing large files unfairly.

**Score bands:**
| Score | Label |
|---|---|
| 0–20 | Clean |
| 21–40 | Slightly Sloppy |
| 41–60 | Sloppy |
| 61–80 | Very Sloppy |
| 81–100 | Slop |

---

## Language Support Roadmap

| Phase | Languages |
|---|---|
| v0.1 | Python |
| v0.2 | JavaScript, TypeScript |
| v0.3 | Java, Go |
| v0.4 | Rust, C, C++ |
| v0.5 | Kotlin, Swift, Ruby |

Categories S1–S13 are language-agnostic in definition. Detection rules are implemented per language in the static engine.

---

## Open Questions

- [x] Should `S7 Void Abstraction` be disabled by default? → **Default ON, severity LOW**. Delegation pattern looks identical but is intentional; LOW severity lets user decide whether to act.
- [x] How to handle generated boilerplate (e.g., ORM models, protobuf stubs) — exclude from scoring? → **Default excluded via `--ignore` glob patterns**. User specifies paths (e.g. `--ignore "models/*,*_pb2.py"`). No auto-detection.
- [ ] Multi-file clone detection (S5) in a future version?
- [ ] Should S9 threshold differ between scripts vs. library code?
