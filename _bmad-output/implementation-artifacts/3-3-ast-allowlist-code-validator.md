# Story 3.3: AST Allowlist Code Validator

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want generated code validated for syntax errors and unsafe operations before execution,
so that malicious or broken code never reaches the subprocess.

## Acceptance Criteria

1. **Given** generated code, **When** `validate_code()` runs in `pipeline/nodes/validator.py`, **Then** it returns a `tuple[bool, list[str]]` — `(True, [])` for valid code, `(False, [errors])` for invalid

2. **Given** code with a syntax error, **When** `validate_code()` runs, **Then** it returns `(False, ["Syntax error: ..."])` without executing anything

3. **Given** code containing an import outside the allowlist (e.g., `import os`, `import socket`), **When** `validate_code()` runs, **Then** it returns `(False, [error_message])` — only `pandas`, `numpy`, `matplotlib`, `matplotlib.pyplot`, `math`, `statistics`, `datetime`, `collections`, `itertools`, `io`, `base64` are permitted

4. **Given** code containing blocked patterns (`eval()`, `exec()`, `__import__()`, `open()`, `os.*`, `sys.*`, `subprocess.*`, `socket.*`, `urllib.*`, `requests.*`), **When** `validate_code()` runs, **Then** it returns `(False, [error_message])`

5. **Given** clean code with only allowed imports and no blocked patterns, **When** `validate_code()` runs, **Then** it returns `(True, [])`

6. **Given** a validation failure `(False, errors)`, **When** the pipeline processes the result (Story 3.5 wiring), **Then** `translate_error()` is called on the error, `retry_count` is incremented, and the pipeline routes back to `generate_code`

## Tasks / Subtasks

- [x] Task 1: Implement `validate_code(code: str) -> tuple[bool, list[str]]` in `pipeline/nodes/validator.py` (AC: #1–5)
  - [x] 1.1: Replace the `validate_code(state: PipelineState) -> dict` stub with two functions: the pure validator `validate_code(code: str) -> tuple[bool, list[str]]` and a thin LangGraph node wrapper `validate_code_node(state: PipelineState) -> dict`
  - [x] 1.2: Add AST syntax check first — `ast.parse(code)` wrapped in `try/except SyntaxError`; on failure return `(False, ["Syntax error: {e}"])`
  - [x] 1.3: Walk the AST and check all `Import` / `ImportFrom` nodes against the ALLOWED_IMPORTS set; on violation return `(False, ["Blocked import: '{name}'. Only these imports are allowed: pandas, numpy, matplotlib, matplotlib.pyplot, math, statistics, datetime, collections, itertools, io, base64"])`
  - [x] 1.4: Walk the AST and check for blocked function calls and attribute access: `eval`, `exec`, `__import__`; any `os.*`, `sys.*`, `subprocess.*`, `socket.*`, `urllib.*`, `requests.*` attribute access; `open()` call; return `(False, ["Blocked operation: ..."])` on any match
  - [x] 1.5: If all checks pass, return `(True, [])`
  - [x] 1.6: Implement `validate_code_node(state: PipelineState) -> dict` that calls `validate_code(state["generated_code"])`, translates errors via `translate_error(AllowlistViolationError(...))` for allowlist/blocked-op failures and `translate_error(SyntaxError(...))` for syntax failures, and returns `{"validation_errors": errors, "execution_success": False}` on failure or `{"validation_errors": []}` on success

- [x] Task 2: Write unit tests in `tests/test_validator.py` (AC: #1–5)
  - [x] 2.1: Test valid clean code → `(True, [])`
  - [x] 2.2: Test syntax error → `(False, ["Syntax error: ..."])`
  - [x] 2.3: Test each blocked import individually: `import os`, `import socket`, `import subprocess`, `import urllib`, `import requests`, `from os import path`, `import sys`
  - [x] 2.4: Test each blocked call: `eval(...)`, `exec(...)`, `__import__(...)`, `open(...)`
  - [x] 2.5: Test blocked attribute patterns: `os.getcwd()`, `sys.exit()`, `subprocess.run(...)`, `socket.connect()`, `urllib.request.urlopen()`, `requests.get()`
  - [x] 2.6: Test each allowed import is permitted: `import pandas`, `import numpy`, `import matplotlib`, `import matplotlib.pyplot as plt`, `import math`, `import statistics`, `import datetime`, `import collections`, `import itertools`, `import io`, `import base64`
  - [x] 2.7: Test that `from pandas import DataFrame` and `from matplotlib import pyplot as plt` are also allowed (allowlist covers submodule `from` imports)
  - [x] 2.8: Test multiple violations return all errors (not just first one)
  - [x] 2.9: Test `validate_code_node` returns correct dict structure on failure and success (mock `generate_code` output in state)
  - [x] 2.10: Test no `streamlit` import in `pipeline/nodes/validator.py` via `ast.parse()` static guard

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Replacing the `validate_code(state: PipelineState) -> dict` stub in `pipeline/nodes/validator.py` with:
  1. `validate_code(code: str) -> tuple[bool, list[str]]` — the pure AST validator (what the AC and architecture describe)
  2. `validate_code_node(state: PipelineState) -> dict` — thin LangGraph node wrapper that calls the pure validator
- Implementing the AST-based allowlist checking (imports + blocked calls/attributes)
- Writing comprehensive unit tests in `tests/test_validator.py`
- Wiring `translate_error()` for syntax and allowlist failures within the node wrapper

**IS NOT:**
- Implementing the subprocess sandbox executor (`pipeline/nodes/executor.py`) — that is Story 3.4
- Wiring the full LangGraph graph or retry/replan loop (`pipeline/graph.py`) — that is Story 3.5
- Any changes to `streamlit_app.py`
- Changes to `utils/error_translation.py` — `AllowlistViolationError` is already defined there (Story 3.1)

### Design Resolution: validate_code Signature

The existing stub `validate_code(state: PipelineState) -> dict` conflicts with:
- The AC which says `validate_code()` returns `tuple[bool, list[str]]`
- The architecture pattern in `architecture.md#Format Patterns` which shows `validate_code(code: str) -> tuple[bool, list[str]]` called from within a node context

**Resolution:** Replace the stub with two functions in `validator.py`:

```python
# The pure validator — matches AC and architecture pattern
def validate_code(code: str) -> tuple[bool, list[str]]:
    ...

# The LangGraph node wrapper — replaces the stub's signature
def validate_code_node(state: PipelineState) -> dict:
    is_valid, errors = validate_code(state["generated_code"])
    ...
```

Story 3.5 (`pipeline/graph.py`) will wire `validate_code_node` as the graph node — not `validate_code`.

### Current State (After Story 3.2)

**`pipeline/nodes/validator.py` — existing stub:**
```python
def validate_code(state: PipelineState) -> dict:
    # TODO: implement in Story 3.3
    raise NotImplementedError("validate_code() implemented in Story 3.3")
```

**`utils/error_translation.py` — fully implemented (Story 3.1) — relevant parts:**
```python
class AllowlistViolationError(Exception):
    """Raised by validate_code() when generated code contains an import or
    operation outside the permitted allowlist."""
    pass

def translate_error(exception: Exception) -> str:
    # SyntaxError → "Generated code had a syntax error — retrying with a corrected approach."
    # AllowlistViolationError → "Generated code used a restricted operation — retrying with safer code."
    ...
```

**Test suite baseline:** 147 tests, 0 failures. This story must preserve that baseline.

**Pipeline nodes currently implemented:**
- `pipeline/nodes/intent.py` — `classify_intent()` ✅ (Story 2.1)
- `pipeline/nodes/planner.py` — `generate_plan()` ✅ (Story 2.2)
- `pipeline/nodes/codegen.py` — `generate_code()` ✅ (Story 3.2)
- `pipeline/nodes/validator.py` — `validate_code()` ❌ stub → **this story**
- `pipeline/nodes/executor.py` — `execute_code()` ❌ stub → Story 3.4
- `pipeline/nodes/reporter.py` — `render_report()` ❌ stub → Story 3.6
- `pipeline/graph.py` — `run_pipeline()` ❌ stub → Story 3.5

### Required Implementation

**`pipeline/nodes/validator.py` — target after Story 3.3:**

```python
# pipeline/nodes/validator.py
"""AST allowlist code validator node.

NOTE: Never import streamlit in this file.
"""
import ast

from pipeline.state import PipelineState
from utils.error_translation import AllowlistViolationError, translate_error

# Exact set of permitted top-level module names
ALLOWED_IMPORTS = {
    "pandas",
    "numpy",
    "matplotlib",
    "matplotlib.pyplot",
    "math",
    "statistics",
    "datetime",
    "collections",
    "itertools",
    "io",
    "base64",
}

# Blocked function/attribute names called directly
BLOCKED_CALLS = {"eval", "exec", "__import__", "open"}

# Blocked top-level attribute access namespaces
BLOCKED_NAMESPACES = {"os", "sys", "subprocess", "socket", "urllib", "requests"}


def validate_code(code: str) -> tuple[bool, list[str]]:
    """Validate generated code for syntax errors and unsafe operations.

    Returns (True, []) if valid.
    Returns (False, [error_messages]) listing all violations found.
    Uses Python ast module — never executes the code.
    """
    errors: list[str] = []

    # Step 1: Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    # Step 2: Walk AST for violations
    for node in ast.walk(tree):

        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                # Allow if the import name or its root package is in the allowlist
                if name not in ALLOWED_IMPORTS and name.split(".")[0] not in ALLOWED_IMPORTS:
                    errors.append(
                        f"Blocked import: '{name}'. Only these imports are allowed: "
                        + ", ".join(sorted(ALLOWED_IMPORTS))
                    )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if module not in ALLOWED_IMPORTS and root not in ALLOWED_IMPORTS:
                errors.append(
                    f"Blocked import: 'from {module} import ...'. Only these imports are allowed: "
                    + ", ".join(sorted(ALLOWED_IMPORTS))
                )

        # Check blocked function calls: eval(), exec(), __import__(), open()
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                errors.append(f"Blocked operation: '{node.func.id}()' is not permitted.")

            # Check attribute calls on blocked namespaces: os.*, sys.*, subprocess.*, etc.
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in BLOCKED_NAMESPACES:
                        errors.append(
                            f"Blocked operation: '{node.func.value.id}.{node.func.attr}()' is not permitted."
                        )

    if errors:
        return False, errors
    return True, []


def validate_code_node(state: PipelineState) -> dict:
    """LangGraph node wrapper for validate_code.

    Calls validate_code() on state['generated_code'], translates any errors
    through translate_error(), and returns only changed keys per LangGraph convention.
    """
    code = state.get("generated_code", "")
    is_valid, errors = validate_code(code)

    if not is_valid:
        # Translate each error to a user-friendly message
        # Classify error type: syntax errors produce SyntaxError messages,
        # allowlist/blocked-op errors produce AllowlistViolationError messages
        translated_errors = []
        for err in errors:
            if err.startswith("Syntax error:"):
                translated = translate_error(SyntaxError(err))
            else:
                translated = translate_error(AllowlistViolationError(err))
            translated_errors.append(translated)

        existing_errors = list(state.get("error_messages", []))
        return {
            "validation_errors": errors,
            "execution_success": False,
            "error_messages": existing_errors + translated_errors,
        }

    return {"validation_errors": []}
```

### Architecture Compliance Requirements

- **Module boundary:** `pipeline/nodes/validator.py` MUST NOT import `streamlit` — pure pipeline module
- **Pure validator return type:** `validate_code(code: str) -> tuple[bool, list[str]]` — matches architecture format pattern
- **LangGraph node return:** `validate_code_node` returns only changed keys — never `{**state, ...}`
- **Error translation:** All validation failures must route through `translate_error()` from `utils/error_translation.py`
  - Syntax failures → `translate_error(SyntaxError(...))`  → "Generated code had a syntax error — retrying with a corrected approach."
  - Allowlist/blocked failures → `translate_error(AllowlistViolationError(...))` → "Generated code used a restricted operation — retrying with safer code."
- **`AllowlistViolationError` import path:** `from utils.error_translation import AllowlistViolationError` — already confirmed working from Story 3.1
- **AST-only validation:** Never execute or eval the code — use `ast.parse()` and `ast.walk()` only
- **Multiple violations:** Return ALL errors found in a single pass, not just the first one
- **Security-first:** The validator is Layer 1 of the two-layer security model; the subprocess is Layer 2 (Story 3.4)

### Allowlist — Exact Set

The permitted import names (exact values for `ALLOWED_IMPORTS` set):

| Permitted Import | Also allows `from X import Y` |
|---|---|
| `pandas` | `from pandas import DataFrame`, etc. |
| `numpy` | `from numpy import array`, etc. |
| `matplotlib` | `from matplotlib import figure`, etc. |
| `matplotlib.pyplot` | `from matplotlib.pyplot import plt`, etc. |
| `math` | `from math import sqrt`, etc. |
| `statistics` | `from statistics import mean`, etc. |
| `datetime` | `from datetime import datetime`, etc. |
| `collections` | `from collections import defaultdict`, etc. |
| `itertools` | `from itertools import chain`, etc. |
| `io` | `from io import BytesIO`, etc. |
| `base64` | `from base64 import b64encode`, etc. |

**Blocked namespaces (any attribute access on these is blocked):**
`os`, `sys`, `subprocess`, `socket`, `urllib`, `requests`

**Blocked direct calls:**
`eval()`, `exec()`, `__import__()`, `open()`

### Testing Strategy

Follow the same mock-light test patterns used in `tests/test_error_translation.py` and `tests/test_codegen.py`.

For `validate_code(code: str)` tests — no mocking needed; call with inline code strings directly.

For `validate_code_node(state)` tests — pass a minimal state dict and verify the returned dict keys.

For the no-streamlit guard — use `ast.parse()` on `pipeline/nodes/validator.py` source, same as `test_codegen.py`.

**Critical edge cases to cover:**
- Empty string `""` — should parse but be valid (no imports, no blocked calls) → `(True, [])`
- `from pandas import *` — allowed (pandas is in allowlist)
- `from os import path` — blocked (`os` not in allowlist)
- `import matplotlib.pyplot as plt` — allowed (`matplotlib.pyplot` is in allowlist)
- Code using `open()` with no explicit write mode — still blocked (architecture changed from "write modes only" to "open() entirely" in Story 3.2 code review)
- Multiple violations in same code — all returned, not just first

### Previous Story Intelligence (from Story 3.2)

Key patterns and learnings carried forward:

- **Test count baseline:** 147 tests, 0 failures (after Story 3.2 + code review) — MUST be preserved
- **`AllowlistViolationError` location:** `utils/error_translation.py` — confirmed; import path: `from utils.error_translation import AllowlistViolationError, translate_error`
- **`translate_error()` import path:** `from utils.error_translation import translate_error` — confirmed working
- **Story 3.2 code review lesson:** `open()` is blocked entirely (not just write modes) — architecture.md was updated; codegen system prompt was updated too. Apply this exact rule to the validator
- **LangGraph node return convention:** Only return changed keys — never `{**state, "key": value}`
- **Test approach for module boundary:** Use `ast.parse()` on source file as static analysis guard — same as `test_codegen.py::test_generate_code_no_streamlit_import`
- **Code review lesson from Story 3.2:** Include edge cases like `None` or `0` values that would trip falsy checks — for validator, test empty string input
- **Existing stub:** The stub raises `NotImplementedError` — Story 3.3 replaces the entire stub with the two-function design

### Git Intelligence

Recent commits (for regression awareness):
- `00618e91` — "Implemented epic-2 defined in sprint-status.yaml" (Stories 2.1, 2.2, 2.3)
- Stories 3.1 and 3.2 implemented locally (committed together or separately)

**Files that must NOT be broken by Story 3.3:**
- `pipeline/nodes/intent.py` — `classify_intent()` — no changes
- `pipeline/nodes/planner.py` — `generate_plan()` — no changes
- `pipeline/nodes/codegen.py` — `generate_code()` — no changes (validator does NOT call codegen)
- `utils/error_translation.py` — no changes (only read from here; `AllowlistViolationError` already defined)
- `utils/session.py` — no changes
- `streamlit_app.py` — no changes needed
- All existing test files — do not modify, only add new

### Project Structure Notes

**Files to create/modify in Story 3.3:**
- `pipeline/nodes/validator.py` — replace `NotImplementedError` stub with full implementation (two functions)
- `tests/test_validator.py` — create new unit test file

**No changes to:**
- `pipeline/nodes/executor.py` — Story 3.4 scope
- `pipeline/graph.py` — Story 3.5 scope (wires `validate_code_node` as graph node)
- Any `utils/` file — no changes needed
- `streamlit_app.py` — no changes needed
- Any existing test file — do not modify, only add new

**Alignment with architecture:**
- `pipeline/nodes/validator.py` has no streamlit import ✅
- `validate_code(code: str) -> tuple[bool, list[str]]` matches architecture Format Patterns ✅
- `validate_code_node(state: PipelineState) -> dict` returns only changed keys ✅
- Routes exceptions through `translate_error()` ✅
- Uses `AllowlistViolationError` from `utils/error_translation.py` ✅
- `ALLOWED_IMPORTS` set matches the exact list in architecture.md and epics.md ✅
- `open()` is blocked entirely (Story 3.2 code review update) ✅

### References

- Epic 3, Story 3.3 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-33-ast-allowlist-code-validator]
- Architecture — two-layer security model: [Source: _bmad-output/planning-artifacts/architecture.md#authentication--security]
- Architecture — AST allowlist format pattern: [Source: _bmad-output/planning-artifacts/architecture.md#format-patterns]
- Architecture — error translation pattern: [Source: _bmad-output/planning-artifacts/architecture.md#communication-patterns]
- Architecture — module boundaries: [Source: _bmad-output/planning-artifacts/architecture.md#architectural-boundaries]
- `AllowlistViolationError` definition: [utils/error_translation.py](utils/error_translation.py)
- Existing stub to replace: [pipeline/nodes/validator.py](pipeline/nodes/validator.py)
- Pattern reference for node wrapper: [pipeline/nodes/codegen.py](pipeline/nodes/codegen.py)
- Error translation utility: [utils/error_translation.py](utils/error_translation.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Replaced `validate_code(state: PipelineState) -> dict` stub in `pipeline/nodes/validator.py` with two-function design: `validate_code(code: str) -> tuple[bool, list[str]]` (pure AST validator matching AC) and `validate_code_node(state: PipelineState) -> dict` (LangGraph node wrapper, to be wired in Story 3.5).
- Added `_get_root_name()` private helper to walk chained attribute access (`urllib.request.urlopen` etc.) up to the root `ast.Name` identifier — required to catch deep namespace calls.
- `ALLOWED_IMPORTS` is a `frozenset` matching the exact 11-module allowlist from architecture.md. Validation checks both the full dotted name and the root package (e.g. `matplotlib.pyplot` root is `matplotlib`, both are allowed).
- `BLOCKED_CALLS` covers `eval`, `exec`, `__import__`, `open` (fully blocked — no write-mode exception, following Story 3.2 code review update).
- `BLOCKED_NAMESPACES` covers `os`, `sys`, `subprocess`, `socket`, `urllib`, `requests` — attribute calls with these as root identifier are blocked.
- All violations are collected in a single AST walk and returned together (not just first violation).
- `validate_code_node` translates syntax errors via `translate_error(SyntaxError(...))` → "Generated code had a syntax error — retrying with a corrected approach." and allowlist/blocked-op errors via `translate_error(AllowlistViolationError(...))` → "Generated code used a restricted operation — retrying with safer code."
- `validate_code_node` appends translated errors to `state["error_messages"]` (preserves existing messages), and returns only changed keys per LangGraph convention.
- Created `tests/test_validator.py` with 55 unit tests covering: valid code, empty string, syntax errors, all 10 blocked imports individually, all 11 allowed imports, all 4 blocked calls, all 6 blocked namespace patterns (including chained `urllib.request.urlopen`), multiple-violation accumulation, validate_code_node dict structure (10 tests), and no-streamlit AST guard.
- Full regression suite: **202 tests, 0 failures** (147 pre-existing + 55 new). Zero regressions.

**Code Review Fixes (2026-03-11):**
- **H1 fixed:** Added pre-pass to collect call-func attribute ids, then added `ast.Attribute` check (non-call) in main walk — catches `f = os.system` reference-then-call bypass pattern. No double-reporting for call cases.
- **H2 fixed:** Added `test_from_matplotlib_import_pyplot_allowed` covering `from matplotlib import pyplot as plt` — the exact form specified in Task 2.7 that was previously missing.
- **M1 fixed:** Error message for namespace attribute calls now uses specific method name: `'{root_name}.{node.func.attr}()'` instead of generic `'{root_name}.*()'` — more actionable for LLM self-correction in Story 3.5.
- **M4 fixed:** `test_validator_no_streamlit_import` now resolves validator path via `pathlib.Path(__file__).parent.parent / ...` — CWD-independent, safe for CI.
- **L1 fixed:** `test_os_attribute_call_blocked` updated to use `os.getcwd()` as spec'd in Task 2.5.
- Final suite: **204 tests, 0 failures** (57 validator tests).

### File List

- `pipeline/nodes/validator.py` — replaced `NotImplementedError` stub with full implementation
- `tests/test_validator.py` — replaced placeholder with 55 unit tests

### Change Log

- Implemented Story 3.3: AST Allowlist Code Validator (Date: 2026-03-11)
