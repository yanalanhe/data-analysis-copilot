# Story 3.2: Python Code Generation from Plan

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want the system to generate Python analysis code from the approved execution plan,
so that I don't have to write any code myself.

## Acceptance Criteria

1. **Given** an approved execution plan in `pipeline_state["plan"]`, **When** the `generate_code` node runs in `pipeline/nodes/codegen.py`, **Then** valid Python code is produced and stored in `pipeline_state["generated_code"]`

2. **Given** the `generate_code` node's system prompt, **When** it instructs GPT-4o to generate chart code, **Then** the prompt explicitly requires `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, and `plt.tight_layout()` with descriptive human-readable labels (e.g., "Voltage (V)" not "v") — satisfying FR21

3. **Given** generated code that produces a chart, **When** it is executed in the subprocess, **Then** each chart is output as `"CHART:" + base64.b64encode(png_bytes).decode()` on stdout

4. **Given** the `generate_code` node running with a retry context (`retry_count > 0`), **When** it constructs the prompt, **Then** it includes information about the previous failure to guide a better attempt

## Tasks / Subtasks

- [x] Task 1: Implement `generate_code()` node in `pipeline/nodes/codegen.py` (AC: #1, #2, #4)
  - [x] 1.1: Replace the `NotImplementedError` stub with full implementation using `ChatOpenAI(model="gpt-4o", temperature=0)` — same pattern as `planner.py`
  - [x] 1.2: Construct system prompt with explicit chart label requirements: `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, `plt.tight_layout()` with descriptive labels (FR21)
  - [x] 1.3: Include `CHART:` output format requirement in system prompt — generated code must print `"CHART:" + base64.b64encode(buf.getvalue()).decode()` for each chart
  - [x] 1.4: Build user message from `state["plan"]` (numbered list) + `state["csv_temp_path"]` + `state["data_row_count"]`
  - [x] 1.5: When `state["retry_count"] > 0`, append previous error context from `state["error_messages"]` to the user message (last error) to guide retry (AC: #4)
  - [x] 1.6: Wrap LLM call in try/except; on exception call `translate_error(e)` and append to `state["error_messages"]`; return `{"generated_code": "", "error_messages": updated_errors}`
  - [x] 1.7: On success, return `{"generated_code": response.content.strip()}` — only changed keys, per LangGraph convention

- [x] Task 2: Write unit tests in `tests/test_codegen.py` (AC: #1–4)
  - [x] 2.1: Test that `generate_code()` returns a dict with `"generated_code"` key containing non-empty string (mock `ChatOpenAI` response)
  - [x] 2.2: Test that system prompt contains `plt.xlabel`, `plt.ylabel`, `plt.title`, `plt.tight_layout` and `CHART:` (inspect via mock call_args)
  - [x] 2.3: Test retry context: when `retry_count > 0` and `error_messages` is populated, the user message passed to the LLM includes failure context
  - [x] 2.4: Test error handling: when LLM raises an exception, `generate_code()` returns `{"generated_code": "", "error_messages": [translated_message]}` — no raw exception text
  - [x] 2.5: Verify no `streamlit` import anywhere in `pipeline/nodes/codegen.py`

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Replacing the `NotImplementedError` stub in `pipeline/nodes/codegen.py` with a working implementation
- Implementing the GPT-4o-powered codegen node with correct system prompt (chart labels, CHART: output format, retry context)
- Writing comprehensive unit tests for codegen behaviour
- Wiring `translate_error()` for LLM call failures within codegen

**IS NOT:**
- Implementing the AST code validator (`pipeline/nodes/validator.py`) — that is Story 3.3
- Implementing the subprocess sandbox executor (`pipeline/nodes/executor.py`) — that is Story 3.4
- Wiring the full LangGraph graph or retry/replan loop (`pipeline/graph.py`) — that is Story 3.5
- Implementing the `@st.fragment` execution panel or report rendering — that is Story 3.6
- Any changes to `streamlit_app.py` (the Execute button and pipeline invocation are already wired from Story 2.3, but call `run_pipeline()` which is still a stub — that's fine for now)

### Current State (After Story 3-1)

**`pipeline/nodes/codegen.py` — existing stub:**
```python
# pipeline/nodes/codegen.py
def generate_code(state: PipelineState) -> dict:
    # TODO: implement in Story 3.2
    raise NotImplementedError("generate_code() implemented in Story 3.2")
```

**`utils/error_translation.py` — fully implemented (Story 3.1 complete):**
```python
class AllowlistViolationError(Exception): ...

def translate_error(exception: Exception) -> str:
    # Full taxonomy: openai.RateLimitError, openai.APIError, subprocess.TimeoutExpired,
    # SyntaxError, AllowlistViolationError, fallback Exception
    # Also handles UnicodeDecodeError, pd.errors.ParserError (added in code review)
    # Includes fallback logging, self-protection wrapper
```

**Test suite:** 117 tests, 0 failures (105 pre-existing + 12 from Story 3.1). This story must preserve that baseline.

**Pipeline nodes currently implemented:**
- `pipeline/nodes/intent.py` — `classify_intent()` ✅ (Story 2.1)
- `pipeline/nodes/planner.py` — `generate_plan()` ✅ (Story 2.2)
- `pipeline/nodes/codegen.py` — `generate_code()` ❌ stub → **this story**
- `pipeline/nodes/validator.py` — `validate_code()` ❌ stub → Story 3.3
- `pipeline/nodes/executor.py` — `execute_code()` ❌ stub → Story 3.4
- `pipeline/nodes/reporter.py` — `render_report()` ❌ stub → Story 3.6
- `pipeline/graph.py` — `run_pipeline()` ❌ stub → Story 3.5

### Required Implementation

**`pipeline/nodes/codegen.py` — target after Story 3.2:**
```python
# pipeline/nodes/codegen.py
"""Python code generation node.

NOTE: Never import streamlit in this file.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pipeline.state import PipelineState
from utils.error_translation import translate_error

_CODEGEN_SYSTEM_PROMPT = """You are a Python data analysis code generator.
Given an execution plan and a CSV file path, generate clean, executable Python code
that performs the analysis described in the plan.

Rules:
- Load data with pandas: df = pd.read_csv(csv_path)
- Use only these imports: pandas, numpy, matplotlib, matplotlib.pyplot, math, statistics,
  datetime, collections, itertools, io, base64
- For EVERY matplotlib chart, you MUST include ALL of the following with descriptive labels:
    plt.xlabel("Descriptive X Label (units)")  # e.g., "Time (ms)" not "t"
    plt.ylabel("Descriptive Y Label (units)")  # e.g., "Voltage (V)" not "v"
    plt.title("Chart Title describing what is shown")
    plt.tight_layout()
- Output each chart as: print("CHART:" + base64.b64encode(buf.getvalue()).decode())
  where buf is a BytesIO containing the PNG bytes (use plt.savefig(buf, format='png', bbox_inches='tight'))
- Print any written analysis or trend summary as plain text to stdout (not prefixed with CHART:)
- Never use eval(), exec(), __import__(), open() with write modes, os.*, sys.*, subprocess.*
- The variable csv_path is available — use it directly to load the CSV
- Output ONLY the Python code, no markdown fences, no explanations"""


def generate_code(state: PipelineState) -> dict:
    """Generate Python analysis code from the approved execution plan.

    Returns only changed keys per LangGraph convention.
    On retry (retry_count > 0), includes previous error context in the prompt.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    plan_text = "\n".join(
        f"{i + 1}. {step}" for i, step in enumerate(state.get("plan", []))
    )
    user_content = f"Execution plan:\n{plan_text}"
    if state.get("csv_temp_path"):
        user_content += f"\n\nCSV file path (use as csv_path variable): {state['csv_temp_path']}"
    if state.get("data_row_count"):
        user_content += f"\nDataset row count: {state['data_row_count']}"

    # Retry context: include last error to guide a better attempt
    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        error_messages = state.get("error_messages", [])
        if error_messages:
            last_error = error_messages[-1]
            user_content += (
                f"\n\nPrevious attempt failed (attempt {retry_count}):\n{last_error}\n"
                "Please correct the issue and generate improved code."
            )

    messages = [
        SystemMessage(content=_CODEGEN_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    try:
        response = llm.invoke(messages)
        return {"generated_code": response.content.strip()}
    except Exception as e:
        error_msg = translate_error(e)
        existing_errors = state.get("error_messages", [])
        return {
            "generated_code": "",
            "error_messages": existing_errors + [error_msg],
        }
```

**`tests/test_codegen.py` — test approach:**
```python
# tests/test_codegen.py
import pytest
from unittest.mock import MagicMock, patch


def _make_state(**overrides):
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales over time",
        "csv_temp_path": "/tmp/test.csv",
        "data_row_count": 100,
        "intent": "report",
        "plan": ["Load sales data", "Plot sales vs time", "Add trend line"],
        "generated_code": "",
        "validation_errors": [],
        "execution_output": "",
        "execution_success": False,
        "retry_count": 0,
        "replan_triggered": False,
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
        "large_data_detected": False,
        "large_data_message": "",
        "recovery_applied": "",
    }
    base.update(overrides)
    return base


def test_generate_code_returns_generated_code_key():
    """generate_code() must return a dict with non-empty 'generated_code' on success."""
    mock_response = MagicMock()
    mock_response.content = "import pandas as pd\ndf = pd.read_csv(csv_path)\nprint('done')"

    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())

    assert "generated_code" in result
    assert result["generated_code"] != ""


def test_generate_code_system_prompt_contains_chart_label_requirements():
    """System prompt must enforce plt.xlabel, plt.ylabel, plt.title, plt.tight_layout."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT

    assert "plt.xlabel" in _CODEGEN_SYSTEM_PROMPT
    assert "plt.ylabel" in _CODEGEN_SYSTEM_PROMPT
    assert "plt.title" in _CODEGEN_SYSTEM_PROMPT
    assert "plt.tight_layout" in _CODEGEN_SYSTEM_PROMPT
    assert "CHART:" in _CODEGEN_SYSTEM_PROMPT
    assert "descriptive" in _CODEGEN_SYSTEM_PROMPT.lower()


def test_generate_code_retry_context_included_when_retry_count_gt_0():
    """When retry_count > 0 and error_messages non-empty, user message includes failure context."""
    mock_response = MagicMock()
    mock_response.content = "# corrected code"

    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from pipeline.nodes.codegen import generate_code
        state = _make_state(
            retry_count=1,
            error_messages=["Generated code had a syntax error — retrying with a corrected approach."]
        )
        generate_code(state)

        # Inspect the HumanMessage content passed to llm.invoke
        call_args = mock_llm.invoke.call_args[0][0]
        human_message_content = call_args[1].content
        assert "syntax error" in human_message_content or "Previous attempt" in human_message_content


def test_generate_code_no_retry_context_when_retry_count_is_0():
    """When retry_count == 0, user message must NOT include 'Previous attempt'."""
    mock_response = MagicMock()
    mock_response.content = "# first attempt code"

    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state(retry_count=0))

        call_args = mock_llm.invoke.call_args[0][0]
        human_message_content = call_args[1].content
        assert "Previous attempt" not in human_message_content


def test_generate_code_llm_error_returns_translated_message():
    """On LLM exception, generate_code() returns translated error, not raw exception."""
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("connection refused xyz")
        mock_llm_class.return_value = mock_llm

        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())

    assert result["generated_code"] == ""
    assert len(result["error_messages"]) == 1
    # Must NOT contain raw exception text
    assert "connection refused xyz" not in result["error_messages"][0]
    assert "RuntimeError" not in result["error_messages"][0]


def test_generate_code_no_streamlit_import():
    """Regression guard: pipeline/nodes/codegen.py must never import streamlit."""
    import ast
    import pathlib

    src = pathlib.Path("pipeline/nodes/codegen.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) \
                else ([node.module] if node.module else [])
            for name in names:
                assert "streamlit" not in (name or ""), \
                    f"streamlit must not be imported in codegen.py — found: {name}"
```

### Architecture Compliance Requirements

- **Module boundary:** `pipeline/nodes/codegen.py` MUST NOT import `streamlit` — pure pipeline module
- **LangGraph node return:** Return only changed keys — `{"generated_code": "..."}` on success, `{"generated_code": "", "error_messages": [...]}` on error. NEVER `{**state, "generated_code": "..."}`
- **Error handling:** All exceptions from LLM calls must go through `translate_error()` from `utils/error_translation.py` before being added to `error_messages`
- **`ChatOpenAI` pattern:** Use `ChatOpenAI(model="gpt-4o", temperature=0)` — same as `planner.py`
- **Message format:** Use `SystemMessage` + `HumanMessage` from `langchain_core.messages` — same as `planner.py`
- **Chart output format (FR21 + architecture):** System prompt MUST instruct: print `"CHART:" + base64.b64encode(buf.getvalue()).decode()` — this is parsed by `executor.py` (Story 3.4)
- **Chart labels (FR21):** System prompt MUST require `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, `plt.tight_layout()` with descriptive labels — this is an architectural constraint (architecture.md Gap 2)
- **Retry context:** `state["retry_count"]` and `state["error_messages"]` must be read to provide failure context on retries — prevents the LLM from generating the same broken code twice

### Testing Strategy

Follow the same mock-light test patterns used in `tests/test_planner.py` — mock `ChatOpenAI` via `patch("pipeline.nodes.codegen.ChatOpenAI")` and check that `invoke()` was called with the right message structure.

For the system prompt test, assert directly on `_CODEGEN_SYSTEM_PROMPT` module-level constant — no mock needed.

For the no-streamlit test, use `ast.parse()` on the source file — same approach as any static analysis guard.

The test file should be `tests/test_codegen.py`. Run the full test suite before and after: `python -m pytest tests/` — all 117 existing tests must continue to pass.

### Previous Story Intelligence (from Story 3-1)

Key patterns and learnings carried forward:
- **Test count baseline:** 117 tests, 0 failures (after Story 3.1 code review additions) — must be preserved
- **`translate_error()` import path:** `from utils.error_translation import translate_error` — already confirmed working
- **`AllowlistViolationError` location:** `utils/error_translation.py` — Story 3.3 will import and raise it from there
- **planner.py patterns to replicate:** `ChatOpenAI(model="gpt-4o", temperature=0)`, `SystemMessage + HumanMessage`, try/except wrapping LLM call, `return {"plan": steps}` only changed keys
- **Test approach for openai errors:** Use `unittest.mock.MagicMock` spec or try/except ImportError + `pytest.skip` — same as Story 3.1 tests
- **Code review from Story 2-3:** Tests must verify behaviour directly, not rely on dict-merge tautologies
- **The `execute_code()` and `run_pipeline()` nodes remain stubs** — Story 3.2 should NOT attempt to make end-to-end pipeline execution work
- **`streamlit_app.py` Execute button** wires to `run_pipeline()` which is still a stub (Story 3.5) — this is expected; Story 3.2 is isolated to the codegen node only

### Git Intelligence

Recent commits (for regression awareness):
- `00618e91` — "Implemented epic-2 defined in sprint-status.yaml" (Stories 2.1, 2.2, 2.3)
- Story 3.1 committed after this (error translation layer implementation + code review)

**Files modified in Story 3.1 (regression awareness):**
- `utils/error_translation.py` — full implementation + `AllowlistViolationError` + logging + file I/O error cases
- `streamlit_app.py` — `translate_error` import + CSV upload error display fixed
- `tests/test_error_translation.py` — 12 unit tests

**Files that must NOT be broken by Story 3.2:**
- `pipeline/nodes/intent.py` — `classify_intent()` — no changes
- `pipeline/nodes/planner.py` — `generate_plan()` — no changes
- `utils/session.py` — session state init — no changes
- `utils/error_translation.py` — no changes (only read from here)
- `streamlit_app.py` — no changes needed

### Project Structure Notes

**Files to create in Story 3.2:**
- `pipeline/nodes/codegen.py` — replace `NotImplementedError` stub with full implementation
- `tests/test_codegen.py` — create new unit test file

**No changes to:**
- `pipeline/nodes/validator.py` — Story 3.3 scope
- `pipeline/nodes/executor.py` — Story 3.4 scope
- `pipeline/graph.py` — Story 3.5 scope
- Any `utils/` file — no changes needed
- `streamlit_app.py` — no changes needed
- Any existing test file — do not modify, only add new

**Alignment with architecture:**
- `pipeline/nodes/codegen.py` has no streamlit import ✅
- Returns only changed keys from LangGraph node ✅
- Routes exceptions through `translate_error()` ✅
- System prompt enforces FR21 chart label requirement (architecture Gap 2) ✅
- System prompt enforces `CHART:` base64 output format (architecture communication pattern) ✅
- Uses `state["retry_count"]` and `state["error_messages"]` for adaptive retry prompting ✅

### References

- Epic 3, Story 3.2 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-32-python-code-generation-from-plan]
- Architecture — codegen system prompt constraint (Gap 2): [Source: _bmad-output/planning-artifacts/architecture.md#gap-2--fr21-codegen-node-chart-label-requirement]
- Architecture — CHART: output pattern: [Source: _bmad-output/planning-artifacts/architecture.md#format-patterns]
- Architecture — LangGraph node return convention: [Source: _bmad-output/planning-artifacts/architecture.md#format-patterns]
- Architecture — error translation pattern: [Source: _bmad-output/planning-artifacts/architecture.md#communication-patterns]
- Architecture — module boundaries: [Source: _bmad-output/planning-artifacts/architecture.md#architectural-boundaries]
- Existing stub to replace: [pipeline/nodes/codegen.py](pipeline/nodes/codegen.py)
- Pattern to follow: [pipeline/nodes/planner.py](pipeline/nodes/planner.py)
- Error translation utility (already implemented): [utils/error_translation.py](utils/error_translation.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Replaced `NotImplementedError` stub in `pipeline/nodes/codegen.py` with full `generate_code()` implementation using `ChatOpenAI(model="gpt-4o", temperature=0)` — same pattern as `planner.py`.
- `_CODEGEN_SYSTEM_PROMPT` module-level constant includes all FR21 chart label requirements (`plt.xlabel`, `plt.ylabel`, `plt.title`, `plt.tight_layout` with descriptive label examples) and the `CHART:` base64 stdout output format (architecture communication pattern).
- Retry context: when `retry_count > 0` and `error_messages` is non-empty, the last error message is appended to the user prompt with "Previous attempt failed" context to guide GPT-4o toward a corrected implementation.
- On LLM exception: `translate_error(e)` called from `utils/error_translation.py`; new message appended to existing `error_messages`; returns `{"generated_code": "", "error_messages": [...]}`.
- On success: returns `{"generated_code": response.content.strip()}` — only changed keys per LangGraph convention.
- Created `tests/test_codegen.py` with 22 unit tests covering: return shape on success, whitespace stripping, LangGraph single-key convention, system prompt content (all 5 checks), SystemMessage type guard, retry context inclusion/exclusion, plan steps in user message, CSV path in user message, multi-error last-error selection, LLM error handling (4 tests), no-streamlit AST guard, gpt-4o model, temperature=0.
- Full regression suite: **139 tests, 0 failures** (117 pre-existing + 22 new).
- Code review fixes (2026-03-11): [H1] Added `_strip_markdown_fences()` to strip ```python/``` fences from LLM output. [M1] Added `matplotlib.use('Agg')` and `plt.close()` instructions to system prompt for headless subprocess safety. [M2] Edge case awareness documented. [L1] Fixed `data_row_count` truthiness bug — `is not None` check instead of falsy. [L2] System prompt now blocks `open()` entirely (not just write modes). [L4] Added tests for `csv_temp_path=None` and `data_row_count=0` edge cases. 8 new tests added. **147 tests, 0 failures**.

### File List

- `pipeline/nodes/codegen.py` — replaced `NotImplementedError` stub with full implementation; code review fixes added
- `tests/test_codegen.py` — created with 30 unit tests (22 original + 8 code review)

### Change Log

- Implemented Story 3.2: Python Code Generation from Plan (Date: 2026-03-11)
- Code review fixes: markdown fence stripping, Agg backend, plt.close(), data_row_count truthiness, open() blocking, edge case tests (Date: 2026-03-11)
