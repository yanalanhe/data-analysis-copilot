# Story 3.4: Subprocess Sandbox Execution

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want validated code executed in an isolated subprocess with a timeout,
so that generated code cannot affect my machine or persist data outside the session.

## Acceptance Criteria

1. **Given** code that passes all validation checks, **When** `execute_code` runs in `pipeline/nodes/executor.py`, **Then** a per-session temp directory is created via `tempfile.mkdtemp()` and the subprocess runs within it

2. **Given** the subprocess, **When** it runs, **Then** it has no access to the host filesystem outside the temp directory (NFR9) and no parent environment variables except whitelisted `PATH` and `PYTHONPATH` (NFR10)

3. **Given** a subprocess running longer than 60 seconds, **When** the timeout fires, **Then** the subprocess is killed, `subprocess.TimeoutExpired` is caught, `translate_error()` is called, and the message is appended to `pipeline_state["error_messages"]`

4. **Given** successful subprocess execution, **When** stdout is parsed, **Then** lines beginning with `CHART:` are base64-decoded into `bytes` and stored in `pipeline_state["report_charts"]`; remaining stdout text is stored in `pipeline_state["report_text"]`; `pipeline_state["execution_success"]` is set to `True`

5. **Given** execution failure (non-zero exit code or exception), **When** the error is processed, **Then** `pipeline_state["execution_success"]` is set to `False` and a translated error message is appended to `pipeline_state["error_messages"]`

6. **Given** execution completes (success or failure), **When** cleanup runs, **Then** the temp directory is deleted and CSV data does not persist to disk (NFR12)

## Tasks / Subtasks

- [x] Task 1: Implement `execute_code(state: PipelineState) -> dict` in `pipeline/nodes/executor.py` (AC: #1–6)
  - [x] 1.1: Create per-session temp directory using `tempfile.mkdtemp()` at node entry — this is the subprocess working directory
  - [x] 1.2: Write the generated code to a temp `.py` file inside the temp dir (e.g., `analysis.py`)
  - [x] 1.3: Copy the CSV file from `state["csv_temp_path"]` into the temp dir so the subprocess can read it; update any path references in the code to use the temp-dir-relative path (or pass temp dir as cwd)
  - [x] 1.4: Launch subprocess with `subprocess.run([sys.executable, "analysis.py"], cwd=temp_dir, capture_output=True, text=True, timeout=60, env=restricted_env)` — no other env vars inherited (uses sys.executable for cross-platform venv reliability)
  - [x] 1.5: On success (returncode == 0): parse stdout line-by-line — lines starting with `CHART:` → base64-decode the rest → `list[bytes]` into `report_charts`; all other stdout lines → `report_text`; set `execution_success = True`
  - [x] 1.6: On failure (non-zero returncode): translate stderr via `translate_error(Exception(stderr))`, set `execution_success = False`, append translated message to `error_messages`
  - [x] 1.7: Wrap subprocess call in `try/except subprocess.TimeoutExpired` — kill the process, call `translate_error(subprocess.TimeoutExpired(...))`, set `execution_success = False`, append to `error_messages`
  - [x] 1.8: Wrap entire node in `try/except Exception` as outer catch-all — translate via `translate_error(e)`, set `execution_success = False`, append to `error_messages`
  - [x] 1.9: Wrap temp dir cleanup in `finally` block using `shutil.rmtree(temp_dir, ignore_errors=True)` — always runs regardless of success or failure
  - [x] 1.10: Return only changed keys per LangGraph convention: `{"report_charts": ..., "report_text": ..., "execution_success": ..., "error_messages": ...}` (never `{**state, ...}`)

- [x] Task 2: Write integration tests in `tests/test_executor.py` (AC: #1–6)
  - [x] 2.1: Test successful execution with chart output — generated code prints a `CHART:<base64>` line and some text → verify `report_charts` has one bytes item, `report_text` has the text, `execution_success` is `True`
  - [x] 2.2: Test successful execution with only text output (no charts) — `report_charts` is `[]`, `report_text` has content, `execution_success` is `True`
  - [x] 2.3: Test successful execution with multiple CHART: lines — `report_charts` has correct count, all decoded correctly
  - [x] 2.4: Test execution failure (non-zero exit code via `sys.exit(1)` in generated code) → `execution_success` is `False`, `error_messages` has a translated message, `report_charts` is `[]`
  - [x] 2.5: Test timeout handling — mock `subprocess.run` to raise `TimeoutExpired` → `execution_success` is `False`, `error_messages` includes timeout-translated message
  - [x] 2.6: Test temp dir cleanup after success — temp dir does not exist after `execute_code` returns
  - [x] 2.7: Test temp dir cleanup after failure — temp dir does not exist after `execute_code` returns even on error
  - [x] 2.8: Test env isolation — subprocess cannot access arbitrary `os.environ` keys; custom secret not visible to subprocess
  - [x] 2.9: Test that `execute_code` does NOT import streamlit — use `ast.parse()` on `pipeline/nodes/executor.py` source, same guard as other node tests
  - [x] 2.10: Test return dict structure — verify returned dict contains only changed keys and does not spread full state
  - [x] 2.11: Test `report_text` excludes `CHART:` lines — only non-CHART stdout lines appear in `report_text`
  - [x] 2.12: Test `report_text` is stripped of leading/trailing whitespace

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Replacing the `execute_code(state: PipelineState) -> dict` stub in `pipeline/nodes/executor.py` with the full subprocess sandbox implementation
- Per-session `tempfile.mkdtemp()` temp directory isolation (NFR9)
- Env var isolation — only `PATH` and `PYTHONPATH` passed to subprocess (NFR10)
- 60-second execution timeout (NFR3)
- `CHART:<base64>` stdout parsing → `list[bytes]` in `report_charts`
- Temp dir cleanup via `shutil.rmtree` in `finally` block (NFR12)
- Writing integration tests in `tests/test_executor.py` (currently a TODO placeholder)

**IS NOT:**
- Wiring the full LangGraph graph or retry/replan loop (`pipeline/graph.py`) — that is Story 3.5
- Implementing the report panel render in `streamlit_app.py` — that is Story 3.6
- Any changes to `pipeline/nodes/validator.py` — done in Story 3.3
- Any changes to `utils/error_translation.py` — `translate_error()` already handles `subprocess.TimeoutExpired` (Story 3.1)
- Any changes to `streamlit_app.py`

### Current State (After Story 3.3)

**`pipeline/nodes/executor.py` — existing stub:**
```python
def execute_code(state: PipelineState) -> dict:
    """Execute validated code in an isolated subprocess with 60s timeout.

    Full implementation in Story 3.4 (subprocess sandbox execution).
    Uses tempfile.mkdtemp() per session; cleans up after execution.
    Parses stdout for 'CHART:<base64_png>' lines → report_charts.
    Returns only changed keys per LangGraph convention.
    """
    # TODO: implement in Story 3.4
    raise NotImplementedError("execute_code() implemented in Story 3.4")
```

**`tests/test_executor.py` — existing placeholder:**
```python
# tests/test_executor.py
"""Subprocess sandbox integration tests for pipeline/nodes/executor.py.

Full implementation in Story 3.4 (subprocess sandbox execution).
"""
# TODO: implement tests in Story 3.4
```

**`utils/error_translation.py` — fully implemented (Story 3.1) — relevant parts:**
```python
def translate_error(exception: Exception) -> str:
    # subprocess.TimeoutExpired → "Analysis took too long and was stopped. Try a simpler request or subset your data."
    # SyntaxError → "Generated code had a syntax error — retrying with a corrected approach."
    # AllowlistViolationError → "Generated code used a restricted operation — retrying with safer code."
    # All other Exception → "An unexpected error occurred. Check the developer console for details."
    ...
```

**Test suite baseline:** 204 tests, 0 failures (after Story 3.3 + code review). This story must preserve that baseline and add new tests.

**Pipeline nodes currently implemented:**
- `pipeline/nodes/intent.py` — `classify_intent()` ✅ (Story 2.1)
- `pipeline/nodes/planner.py` — `generate_plan()` ✅ (Story 2.2)
- `pipeline/nodes/codegen.py` — `generate_code()` ✅ (Story 3.2)
- `pipeline/nodes/validator.py` — `validate_code()` + `validate_code_node()` ✅ (Story 3.3)
- `pipeline/nodes/executor.py` — `execute_code()` ❌ stub → **this story**
- `pipeline/nodes/reporter.py` — `render_report()` ❌ stub → Story 3.6
- `pipeline/graph.py` — `run_pipeline()` ❌ stub → Story 3.5

### Required Implementation

**`pipeline/nodes/executor.py` — target after Story 3.4:**

```python
# pipeline/nodes/executor.py
"""Subprocess sandbox execution node.

NOTE: Never import streamlit in this file.
"""
import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.state import PipelineState
from utils.error_translation import translate_error


def execute_code(state: PipelineState) -> dict:
    """Execute validated code in an isolated subprocess with 60s timeout.

    Creates a per-session temp dir, runs generated code as a subprocess with
    restricted env vars, parses CHART: lines from stdout, then cleans up.
    Returns only changed keys per LangGraph convention.
    """
    temp_dir = tempfile.mkdtemp()
    report_charts: list[bytes] = []
    report_text: str = ""
    execution_success: bool = False
    existing_errors = list(state.get("error_messages", []))
    new_errors: list[str] = []

    try:
        # Write generated code to a temp file
        code_path = Path(temp_dir) / "analysis.py"
        code_path.write_text(state.get("generated_code", ""), encoding="utf-8")

        # Copy the session CSV into the temp dir so subprocess can read it
        csv_source = state.get("csv_temp_path")
        if csv_source and Path(csv_source).exists():
            import shutil as _shutil
            _shutil.copy2(csv_source, Path(temp_dir) / "data.csv")

        # Restricted env: only PATH and PYTHONPATH
        restricted_env = {}
        if "PATH" in os.environ:
            restricted_env["PATH"] = os.environ["PATH"]
        if "PYTHONPATH" in os.environ:
            restricted_env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        result = subprocess.run(
            ["python", str(code_path)],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60,
            env=restricted_env,
        )

        if result.returncode == 0:
            # Parse stdout: CHART: lines → bytes, everything else → text
            text_lines = []
            for line in result.stdout.split("\n"):
                if line.startswith("CHART:"):
                    chart_bytes = base64.b64decode(line[6:])
                    report_charts.append(chart_bytes)
                else:
                    text_lines.append(line)
            report_text = "\n".join(text_lines).strip()
            execution_success = True
        else:
            stderr = result.stderr.strip() or "Code execution failed with non-zero exit code."
            translated = translate_error(Exception(stderr))
            new_errors.append(translated)
            execution_success = False

    except subprocess.TimeoutExpired as e:
        translated = translate_error(e)
        new_errors.append(translated)
        execution_success = False

    except Exception as e:
        translated = translate_error(e)
        new_errors.append(translated)
        execution_success = False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "report_charts": report_charts,
        "report_text": report_text,
        "execution_success": execution_success,
        "error_messages": existing_errors + new_errors,
    }
```

### Architecture Compliance Requirements

- **Module boundary:** `pipeline/nodes/executor.py` MUST NOT import `streamlit` — pure pipeline module (no `st.session_state` access)
- **LangGraph node return:** Return only changed keys — never `{**state, ...}`. Specifically return `report_charts`, `report_text`, `execution_success`, `error_messages` (merged with existing)
- **Error translation:** ALL exceptions must route through `translate_error()` from `utils/error_translation.py`
  - `subprocess.TimeoutExpired` → "Analysis took too long and was stopped. Try a simpler request or subset your data."
  - All other `Exception` → "An unexpected error occurred. Check the developer console for details."
- **Temp dir:** `tempfile.mkdtemp()` — one new temp dir per `execute_code()` call; cleaned up in `finally`
- **Env isolation:** subprocess `env` kwarg must contain ONLY `PATH` and `PYTHONPATH` — nothing else (no `OPENAI_API_KEY`, no other secrets)
- **Timeout:** `timeout=60` passed to `subprocess.run()` — kills runaway processes
- **CHART: parsing:** Exact prefix `"CHART:"` (6 characters); decode with `base64.b64decode(line[6:])` → `bytes`
- **`report_text`:** All non-CHART stdout lines joined and stripped — never includes CHART: lines
- **CSV path:** The executor passes CSV via copying into temp dir or using `state["csv_temp_path"]` directly as cwd; generated code should reference `"data.csv"` relative to cwd (note: codegen prompt specifies this — no changes needed to codegen)
- **Cleanup:** `shutil.rmtree(temp_dir, ignore_errors=True)` in `finally` — always runs, ignores errors

### Security Model Context

Story 3.4 is **Layer 2** of the two-layer sandbox:

| Layer | What | Where | Story |
|---|---|---|---|
| Layer 1 | AST allowlist — blocks unsafe imports/calls before execution | `pipeline/nodes/validator.py` | 3.3 ✅ Done |
| Layer 2 | Subprocess isolation — restricted cwd, restricted env, timeout | `pipeline/nodes/executor.py` | **3.4 ← this story** |

The AST validator (Story 3.3) ran first — by the time `execute_code()` is called, the code has already passed import and blocked-call checks. The subprocess adds runtime isolation on top.

### Testing Strategy

`test_executor.py` should use **real subprocess execution** (not mocks) — these are integration tests. The subprocess is a key security boundary; mocking it would defeat the purpose of testing isolation.

Use small, self-contained Python code strings that are valid (would pass the AST validator) and produce predictable output:

```python
# Minimal chart-producing code for test fixtures
CHART_CODE = """
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import base64, io

plt.figure()
plt.plot([1, 2, 3], [4, 5, 6])
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Test')
plt.tight_layout()

buf = io.BytesIO()
plt.savefig(buf, format='png', bbox_inches='tight')
print("CHART:" + base64.b64encode(buf.getvalue()).decode())
print("This is trend text.")
"""

# Minimal failing code
FAILING_CODE = """
import sys
sys.exit(1)
"""

# Minimal env leak test code
ENV_LEAK_CODE = """
import os
print(os.environ.get("OPENAI_API_KEY", "NOT_FOUND"))
"""
```

**Note on matplotlib backend:** The subprocess has no display server. Generated code will need `matplotlib.use('Agg')` set before creating figures — this is already in the codegen system prompt (Story 3.2). For tests, set it explicitly in test code strings.

**Note on timeout testing:** Rather than sleeping 120s, patch `subprocess.run` to raise `subprocess.TimeoutExpired` directly in the timeout test. Or use a short `time.sleep()` with a patched `timeout` parameter passed via monkeypatching.

**Critical edge cases:**
- Empty `generated_code` in state → code file written as empty → subprocess exits 0 with empty stdout → `report_charts=[]`, `report_text=""`, `execution_success=True`
- `csv_temp_path` is `None` or file doesn't exist → no CSV copy attempted, subprocess still runs (code may fail if it tries to read `data.csv`, but that's handled by non-zero exit)
- Subprocess outputs only `CHART:` lines with no text → `report_text = ""`
- Subprocess outputs only text with no `CHART:` lines → `report_charts = []`
- Multiple `CHART:` lines → all decoded and collected in order
- `CHART:` line with trailing newline → ensure strip or split handles correctly

### Previous Story Intelligence (from Story 3.3)

Key patterns and learnings carried forward:

- **Test count baseline:** 204 tests, 0 failures — MUST be preserved
- **LangGraph node return convention:** Only return changed keys — never `{**state, "key": value}`
- **Error translation import path:** `from utils.error_translation import translate_error` — confirmed working
- **Module boundary guard test pattern:** Use `ast.parse()` on source file to check for streamlit imports — same pattern as `test_validator.py::test_validator_no_streamlit_import` and `test_codegen.py`
- **`error_messages` accumulation pattern:** `existing_errors = list(state.get("error_messages", [])); return {"error_messages": existing_errors + new_errors}` — preserve existing messages, don't overwrite
- **Story 3.3 code review lessons:**
  - Catch-all error handling should come AFTER specific exception handlers, not before
  - Test for non-CHART lines not leaking into `report_charts`
  - Private helpers should use single underscore prefix: `_parse_stdout()`
- **Validator signature distinction:** `validate_code()` is the pure function; `validate_code_node()` is the LangGraph wrapper. Same pattern applies here: `execute_code()` IS the LangGraph node (no separate wrapper needed — the function IS the node because it takes `state: PipelineState`)

### Git Intelligence

Recent commits:
- `f1db0016` — "Implemented story 3-3-ast-allowlist-code-validator" — last commit; added `validate_code()` + `validate_code_node()` + 57 validator tests
- `c44f5195` — "Implemented epic-3 3-1, 3-2 and 3-3" — error translation, codegen, early validator work
- `00618e91` — "Implemented epic-2" — intent, planner, plan review nodes

**Files that must NOT be broken by Story 3.4:**
- `pipeline/nodes/intent.py` — no changes
- `pipeline/nodes/planner.py` — no changes
- `pipeline/nodes/codegen.py` — no changes
- `pipeline/nodes/validator.py` — no changes
- `utils/error_translation.py` — no changes (only imported, not modified)
- `utils/session.py` — no changes
- `streamlit_app.py` — no changes needed (Story 3.6 wires the fragment panel)
- All existing test files — do not modify, only add new tests to `tests/test_executor.py`

### Project Structure Notes

**Files to create/modify in Story 3.4:**
- `pipeline/nodes/executor.py` — replace `NotImplementedError` stub with full implementation
- `tests/test_executor.py` — replace TODO placeholder with integration tests

**No changes to:**
- `pipeline/nodes/validator.py` — Story 3.3 scope (done)
- `pipeline/graph.py` — Story 3.5 scope (wires `execute_code` as graph node)
- `pipeline/nodes/reporter.py` — Story 3.6 scope
- Any `utils/` file — no changes needed
- `streamlit_app.py` — no changes needed
- Any existing test file — do not modify, only add new

**Alignment with architecture:**
- `pipeline/nodes/executor.py` has no streamlit import ✅
- `execute_code(state: PipelineState) -> dict` returns only changed keys ✅
- Routes exceptions through `translate_error()` ✅
- Uses `tempfile.mkdtemp()` per-session temp dir ✅
- Cleanup via `shutil.rmtree()` in `finally` ✅
- Env isolation: only `PATH` + `PYTHONPATH` ✅
- 60-second timeout enforced ✅
- `CHART:` prefix parsing: `base64.b64decode(line[6:])` ✅
- `templates.json` is never accessible from within subprocess (subprocess cwd is temp dir, not app root) ✅

### References

- Epic 3, Story 3.4 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-34-subprocess-sandbox-execution]
- Architecture — subprocess security layer 2: [Source: _bmad-output/planning-artifacts/architecture.md#authentication--security]
- Architecture — subprocess data flow: [Source: _bmad-output/planning-artifacts/architecture.md#subprocess-data-flow]
- Architecture — CHART: format pattern: [Source: _bmad-output/planning-artifacts/architecture.md#format-patterns]
- Architecture — error translation pattern: [Source: _bmad-output/planning-artifacts/architecture.md#communication-patterns]
- Architecture — module boundaries: [Source: _bmad-output/planning-artifacts/architecture.md#architectural-boundaries]
- Existing stub to replace: [pipeline/nodes/executor.py](pipeline/nodes/executor.py)
- Error translation utility: [utils/error_translation.py](utils/error_translation.py)
- Test placeholder to fill: [tests/test_executor.py](tests/test_executor.py)
- Pattern reference for node: [pipeline/nodes/validator.py](pipeline/nodes/validator.py)
- Pattern reference for test guard: [tests/test_validator.py](tests/test_validator.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `execute_code(state: PipelineState) -> dict` in `pipeline/nodes/executor.py`, replacing the `NotImplementedError` stub with the full subprocess sandbox.
- Added private `_parse_stdout(stdout: str) -> tuple[list[bytes], str]` helper to separate CHART: line decoding from report text collection — clean separation keeps `execute_code` readable.
- Used `sys.executable` (not literal `"python"`) for cross-platform venv reliability; the architecture spec says "subprocess" not "python binary", and `sys.executable` always points to the running interpreter.
- Restricted env: `PATH`, `PYTHONPATH`, `MPLCONFIGDIR=temp_dir`, `MPLBACKEND=Agg`. The two matplotlib vars are needed to allow matplotlib to initialize without `HOME`/`USERPROFILE` (Windows). `MPLCONFIGDIR=temp_dir` routes matplotlib config into the sandbox directory itself — arguably more secure than passing HOME. No API keys or host credentials are passed.
- Temp dir cleanup in `finally` block with `shutil.rmtree(ignore_errors=True)` — runs after success, failure, and timeout. Verified by three separate tests that capture the dir path then confirm it's gone.
- All exceptions route through `translate_error()` — `subprocess.TimeoutExpired` → human-readable timeout message; `Exception` fallback for any other error. No raw reprs ever returned.
- Pre-existing `error_messages` from state are preserved and new errors appended — not overwritten.
- Added 29 tests in `tests/test_executor.py` across 7 test classes: `TestParseStdout` (7 pure unit tests), `TestExecuteCodeSuccess` (6 success scenarios), `TestExecuteCodeFailure` (4 failure scenarios), `TestExecuteCodeTimeout` (2 with mock), `TestExecuteCodeCleanup` (3 cleanup verification), `TestExecuteCodeEnvIsolation` (2 security tests), `TestExecuteCodeReturnStructure` (5 structure/guard tests).
- Full regression suite: **233 tests, 0 failures** (204 pre-existing + 29 new). Zero regressions.
- **Code review fixes applied (2026-03-11):**
  - **H1**: `_parse_stdout()` now wraps `base64.b64decode()` in try/except — malformed CHART: lines are silently skipped instead of crashing
  - **M1**: Added `test_csv_file_copied_and_readable` — creates a real CSV temp file, passes as `csv_temp_path`, verifies subprocess reads `data.csv` with pandas
  - **M2**: `execute_code()` now captures `result.stderr` on success and returns it in `execution_output` for debugging visibility
  - **M3**: Fixed tautological assertion in `test_report_text_is_stripped` (both unit and integration) — now asserts expected value directly (`"hello"` / `""`) instead of `x == x.strip()`
  - Added `test_malformed_chart_line_skipped` to validate H1 fix
  - Updated `test_returns_only_changed_keys` and `test_does_not_spread_full_state` to reflect `execution_output` in return dict
  - Full regression suite: **235 tests, 0 failures** (31 executor tests). Zero regressions.

### File List

- `pipeline/nodes/executor.py` — replaced `NotImplementedError` stub with full `execute_code()` implementation and `_parse_stdout()` helper; code review fixes for malformed CHART: handling and stderr capture
- `tests/test_executor.py` — replaced TODO placeholder with 31 integration/unit tests (29 original + 2 added during code review)

### Change Log

- Implemented Story 3.4: Subprocess Sandbox Execution (Date: 2026-03-11)
- Code review fixes: H1, M1, M2, M3 (Date: 2026-03-11)
