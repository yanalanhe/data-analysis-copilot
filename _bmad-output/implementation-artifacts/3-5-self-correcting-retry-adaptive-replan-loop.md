# Story 3.5: Self-Correcting Retry & Adaptive Replan Loop

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want the system to automatically retry failed code generation up to 3 times and adaptively replan when all retries are exhausted,
so that standard analysis requests succeed without me having to debug or intervene.

## Acceptance Criteria

1. **Given** `pipeline/graph.py` with the compiled LangGraph `StateGraph`, **When** I inspect the node connections, **Then** all nodes are wired: `classify_intent → generate_plan → generate_code → validate_code → execute_code`, with `render_report` connected via conditional edges on `execute_code`

2. **Given** `route_after_execution` in `pipeline/graph.py`, **When** `execution_success` is `True`, **Then** it returns `"render_report"`

3. **Given** `route_after_execution`, **When** `execution_success` is `False` and `retry_count < 3`, **Then** it returns `"generate_code"` and `retry_count` is incremented

4. **Given** `route_after_execution`, **When** `execution_success` is `False` and `retry_count >= 3`, **Then** it returns `"generate_plan"` and `replan_triggered` is set to `True`

5. **Given** `graph.add_conditional_edges` in `pipeline/graph.py`, **When** I inspect the implementation, **Then** it matches exactly: `graph.add_conditional_edges("execute_code", route_after_execution, {"render_report": "render_report", "generate_code": "generate_code", "generate_plan": "generate_plan"})`

6. **Given** any retry or replan event, **When** the error is caught, **Then** a human-readable message is appended to `pipeline_state["error_messages"]` via `translate_error()` — never a raw exception repr

## Tasks / Subtasks

- [x] Task 1: Implement `pipeline/nodes/error_handler.py` — `handle_error()` node (AC: #3, #4, #6)
  - [x] 1.1: Implement `handle_error(state: PipelineState) -> dict` replacing the `NotImplementedError` stub
  - [x] 1.2: Increment `retry_count` by 1: `{"retry_count": state.get("retry_count", 0) + 1}`
  - [x] 1.3: If new `retry_count >= 3`: set `replan_triggered = True` and append replan message to `error_messages`
  - [x] 1.4: If new `retry_count < 3`: append retry message to `error_messages` (e.g., "Retrying code generation (attempt N/3)...")
  - [x] 1.5: Return only changed keys: `{"retry_count": ..., "replan_triggered": ..., "error_messages": ...}`
  - [x] 1.6: Never import streamlit — pure pipeline module

- [x] Task 2: Implement `pipeline/graph.py` — full LangGraph StateGraph and `run_pipeline()` (AC: #1–5)
  - [x] 2.1: Import all nodes: `classify_intent`, `generate_plan`, `generate_code`, `validate_code_node`, `execute_code`, `handle_error`, `render_report`
  - [x] 2.2: Create `StateGraph(PipelineState)` and add all nodes by function name (string must match function name exactly per architecture convention)
  - [x] 2.3: Add `START` entry edge to `"classify_intent"` (using `langgraph.graph.START`)
  - [x] 2.4: Wire linear edges: `classify_intent → generate_plan → generate_code → validate_code_node → execute_code`
    - Use the function name string `"validate_code_node"` (not `"validate_code"`) when adding the node — it is the LangGraph wrapper
  - [x] 2.5: Implement `route_after_execution(state: PipelineState) -> str` routing function:
    - `if state.get("execution_success"): return "render_report"`
    - `elif state.get("retry_count", 0) < 3: return "generate_code"`
    - `else: return "generate_plan"` (retry_count incremented by execute_code on failure)
  - [x] 2.6: `graph.add_conditional_edges("execute_code", route_after_execution, {"render_report": "render_report", "generate_code": "generate_code", "generate_plan": "generate_plan"})` — exact AC5 match
  - [x] 2.7: Add `render_report` → `END` edge (using `langgraph.graph.END`)
  - [x] 2.8: Compile graph: `compiled_graph = _builder.compile()`
  - [x] 2.9: Implement `run_pipeline(state: PipelineState) -> PipelineState`:
    - Wrap invocation in `try/except Exception` for non-blocking error handling (NFR15)
    - Apply `@traceable(name="analysis_pipeline")` from `langsmith` — on `run_pipeline()` ONLY
    - Return `compiled_graph.invoke(state)`
  - [x] 2.10: Ensure graph module-level code runs on import (graph compiled once at module load)
  - [x] 2.11: `pipeline/graph.py` must NEVER import streamlit

- [x] Task 3: Ensure `retry_count` increments correctly through the loop (AC: #3, #4)
  - [x] 3.1: `execute_code` failure paths increment `retry_count` and set `replan_triggered` (Approach A — satisfies AC5 exactly without modifying existing test assertions)
  - [x] 3.2: `generate_code` uses `state.get("retry_count", 0)` and `error_messages[-1]` to guide retry — confirmed in Story 3.2 implementation
  - [x] 3.3: `generate_plan` is re-invoked on adaptive replan path (retry_count >= 3); state has `replan_triggered=True` and accumulated `error_messages` for context

- [x] Task 4: Write tests in `tests/test_graph.py` (AC: #1–6)
  - [x] 4.1: Test graph is importable and `compiled_graph` is a compiled LangGraph graph object
  - [x] 4.2: Test `run_pipeline` is callable and raises no import errors (module-level test, no API call)
  - [x] 4.3: Test `route_after_execution` with `execution_success=True` → returns `"render_report"`
  - [x] 4.4: Test `route_after_execution` with `execution_success=False, retry_count=1` → returns `"generate_code"`
  - [x] 4.5: Test `route_after_execution` with `execution_success=False, retry_count=2` → returns `"generate_code"`
  - [x] 4.6: Test `route_after_execution` with `execution_success=False, retry_count=3` → returns `"generate_plan"`
  - [x] 4.7: Test `handle_error()` with `retry_count=0` → returns `retry_count=1`, `replan_triggered=False`
  - [x] 4.8: Test `handle_error()` with `retry_count=2` → returns `retry_count=3`, `replan_triggered=True`
  - [x] 4.9: Test `handle_error()` preserves and appends to existing `error_messages` — never overwrites
  - [x] 4.10: Test `handle_error()` returns only changed keys (not full state spread)
  - [x] 4.11: Test `graph.py` does NOT import streamlit — use `ast.parse()` on source, same pattern as other node tests
  - [x] 4.12: Test `error_handler.py` does NOT import streamlit
  - [x] 4.13: Test that graph nodes list includes `"classify_intent"`, `"generate_plan"`, `"generate_code"`, `"validate_code_node"`, `"execute_code"`, `"render_report"` (inspect `compiled_graph.nodes`)

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing the full `pipeline/graph.py` LangGraph StateGraph wiring all pipeline nodes (classify_intent → generate_plan → generate_code → validate_code_node → execute_code → [conditional] → render_report / retry / replan)
- Implementing `pipeline/nodes/error_handler.py` `handle_error()` stub with retry count increment and replan flag
- Implementing `route_after_execution()` routing function in `graph.py`
- Implementing `run_pipeline()` with `@traceable` wrapper in `pipeline/graph.py`
- Writing `tests/test_graph.py` from scratch
- Ensuring `retry_count` increments correctly through the self-correction loop

**IS NOT:**
- Implementing `pipeline/nodes/reporter.py` `render_report()` — that is Story 3.6 (still a stub here)
- Rewriting `pipeline/nodes/executor.py` core logic — Story 3.4 scope (done); only adds retry_count/replan_triggered to failure return paths and a validation guard
- Any changes to `pipeline/nodes/codegen.py` — Story 3.2 scope (done; already includes retry context in prompt)
- Any changes to `pipeline/nodes/validator.py` — Story 3.3 scope (done)
- Any UI changes to `streamlit_app.py` — Story 3.6 scope
- Any changes to `utils/` files

### ⚠️ CRITICAL DESIGN DECISION: Two Approaches for AC5

AC5 requires `route_after_execution` to return exactly one of `"render_report"`, `"generate_code"`, or `"generate_plan"` — meaning the conditional edge map is:
```python
graph.add_conditional_edges(
    "execute_code",
    route_after_execution,
    {"render_report": "render_report", "generate_code": "generate_code", "generate_plan": "generate_plan"}
)
```

But `retry_count` must be incremented SOMEWHERE before `route_after_execution` is called. Since routing functions cannot modify state in LangGraph, the increment must happen inside a node.

**Approach A (Recommended — satisfies AC5 exactly):**
- Route from `execute_code` directly to `"generate_code"` or `"generate_plan"` per AC5
- `retry_count` is incremented INSIDE `execute_code` node when execution fails
- Modify `execute_code` (Story 3.4 implementation) to add `retry_count` increment on failure:
  ```python
  # Inside execute_code, on failure path:
  return {
      "execution_success": False,
      "retry_count": state.get("retry_count", 0) + 1,  # NEW in Story 3.5
      "error_messages": ...,
  }
  ```
- `route_after_execution` reads the already-incremented `retry_count`:
  ```python
  def route_after_execution(state: PipelineState) -> str:
      if state.get("execution_success"):
          return "render_report"
      elif state.get("retry_count", 0) < 3:
          return "generate_code"
      else:
          return "generate_plan"
  ```
- `replan_triggered` is set to `True` when `route_after_execution` returns `"generate_plan"` — but routing functions can't set state. So `replan_triggered` is set inside `generate_plan` (add a check there) or inside `execute_code` on the replan path:
  ```python
  if state.get("retry_count", 0) + 1 >= 3:
      return {"execution_success": False, "retry_count": new_count, "replan_triggered": True, ...}
  ```
- `handle_error` node becomes unused in this approach — leave stub as-is

**Approach B (Alternative — uses handle_error):**
- `route_after_execution` routes to `"handle_error"` on failure (not directly to "generate_code"/"generate_plan")
- `handle_error` increments `retry_count`, sets `replan_triggered`, then the graph routes based on that
- Add conditional edges from `handle_error` to `"generate_code"` or `"generate_plan"` based on retry_count
- AC5 check: `graph.add_conditional_edges("execute_code", ...)` routes to `"handle_error"`, not `"generate_code"` — this FAILS AC5

**Conclusion:** **Approach A is required to satisfy AC5 exactly.** Modify `execute_code` to increment `retry_count` and set `replan_triggered` on failure. `handle_error` can remain as a stub (it's not wired in this approach).

### Current State (After Story 3.4)

**`pipeline/graph.py` — existing stub:**
```python
def run_pipeline(state: PipelineState) -> PipelineState:
    """Full implementation in Story 3.5."""
    raise NotImplementedError("run_pipeline() implemented in Story 3.5")
```

**`pipeline/nodes/error_handler.py` — existing stub:**
```python
def handle_error(state: PipelineState) -> dict:
    """Full implementation in Story 3.5."""
    raise NotImplementedError("handle_error() implemented in Story 3.5")
```

**`pipeline/nodes/reporter.py` — still a stub (Story 3.6):**
```python
def render_report(state: PipelineState) -> dict:
    raise NotImplementedError("render_report() implemented in Story 3.6")
```

**`pipeline/nodes/executor.py` — DONE in Story 3.4:**
- Does NOT currently increment `retry_count`
- Returns: `{"report_charts": ..., "report_text": ..., "execution_success": ..., "error_messages": ..., "execution_output": ...}`
- Story 3.5 needs to ADD `retry_count` (and optionally `replan_triggered`) to the return dict on failure path

**`pipeline/nodes/validator.py` — DONE in Story 3.3:**
- `validate_code_node()` is the LangGraph wrapper (not `validate_code` — the pure function)
- On validation failure: sets `execution_success=False`, appends translated error to `error_messages`
- Does NOT increment `retry_count` — this stays as-is for Story 3.5

**Test suite baseline:** 235 tests, 0 failures. This story must preserve that baseline and add new tests.

**Pipeline nodes implemented:**
- `pipeline/nodes/intent.py` — `classify_intent()` ✅ (Story 2.1)
- `pipeline/nodes/planner.py` — `generate_plan()` ✅ (Story 2.2)
- `pipeline/nodes/codegen.py` — `generate_code()` ✅ (Story 3.2) — already handles retry_count context
- `pipeline/nodes/validator.py` — `validate_code()` + `validate_code_node()` ✅ (Story 3.3)
- `pipeline/nodes/executor.py` — `execute_code()` ✅ (Story 3.4) — needs `retry_count` increment added
- `pipeline/nodes/error_handler.py` — `handle_error()` ❌ stub (implement but NOT wire into graph per Approach A)
- `pipeline/nodes/reporter.py` — `render_report()` ❌ stub (NOT implemented here — Story 3.6)
- `pipeline/graph.py` — `run_pipeline()` ❌ stub → **THIS story**

### Required Implementation

#### `pipeline/nodes/executor.py` — Modification (add retry_count on failure)

Modify the failure return paths in `execute_code()` to include `retry_count` increment:

```python
def execute_code(state: PipelineState) -> dict:
    """Execute validated code in an isolated subprocess with 60s timeout."""
    temp_dir = tempfile.mkdtemp()
    report_charts: list[bytes] = []
    report_text: str = ""
    execution_success: bool = False
    existing_errors = list(state.get("error_messages", []))
    new_errors: list[str] = []
    current_retry = state.get("retry_count", 0)

    try:
        # ... (all existing subprocess logic unchanged) ...

        if result.returncode == 0:
            # ... (parse stdout, set execution_success=True) ...
            return {
                "report_charts": report_charts,
                "report_text": report_text,
                "execution_success": True,
                "error_messages": existing_errors + new_errors,
                "execution_output": result.stderr.strip() if result.stderr else "",
            }
        else:
            # FAILURE PATH — increment retry_count
            stderr = result.stderr.strip() or "Code execution failed with non-zero exit code."
            translated = translate_error(Exception(stderr))
            new_errors.append(translated)
            new_retry = current_retry + 1
            return {
                "report_charts": [],
                "report_text": "",
                "execution_success": False,
                "retry_count": new_retry,
                "replan_triggered": new_retry >= 3,
                "error_messages": existing_errors + new_errors,
                "execution_output": stderr,
            }

    except subprocess.TimeoutExpired as e:
        translated = translate_error(e)
        new_errors.append(translated)
        new_retry = current_retry + 1
        return {
            "execution_success": False,
            "retry_count": new_retry,
            "replan_triggered": new_retry >= 3,
            "error_messages": existing_errors + new_errors,
        }

    except Exception as e:
        translated = translate_error(e)
        new_errors.append(translated)
        new_retry = current_retry + 1
        return {
            "execution_success": False,
            "retry_count": new_retry,
            "replan_triggered": new_retry >= 3,
            "error_messages": existing_errors + new_errors,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**IMPORTANT:** The existing 235 tests must still pass after this modification. Adding extra keys to return dicts should be backwards compatible with existing tests. Verify tests do not assert on the ABSENCE of keys.

#### `pipeline/graph.py` — Full Implementation

```python
# pipeline/graph.py
"""LangGraph pipeline graph construction and run_pipeline entry point.

NOTE: Never import streamlit in this file.
"""
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from pipeline.nodes.codegen import generate_code
from pipeline.nodes.executor import execute_code
from pipeline.nodes.intent import classify_intent
from pipeline.nodes.planner import generate_plan
from pipeline.nodes.reporter import render_report
from pipeline.nodes.validator import validate_code_node
from pipeline.state import PipelineState

try:
    from langsmith import traceable
except ImportError:
    def traceable(name=None):  # fallback if langsmith not installed
        def decorator(fn):
            return fn
        return decorator


def route_after_execution(state: PipelineState) -> str:
    """Conditional routing after execute_code.

    Returns:
        "render_report"  — on successful execution
        "generate_code"  — on failure with retry_count < 3 (retry path)
        "generate_plan"  — on failure with retry_count >= 3 (adaptive replan path)
    """
    if state.get("execution_success"):
        return "render_report"
    elif state.get("retry_count", 0) < 3:
        return "generate_code"
    else:
        return "generate_plan"


# Build graph
_graph = StateGraph(PipelineState)

# Add all nodes
_graph.add_node("classify_intent", classify_intent)
_graph.add_node("generate_plan", generate_plan)
_graph.add_node("generate_code", generate_code)
_graph.add_node("validate_code_node", validate_code_node)
_graph.add_node("execute_code", execute_code)
_graph.add_node("render_report", render_report)

# Linear edges
_graph.add_edge(START, "classify_intent")
_graph.add_edge("classify_intent", "generate_plan")
_graph.add_edge("generate_plan", "generate_code")
_graph.add_edge("generate_code", "validate_code_node")
_graph.add_edge("validate_code_node", "execute_code")

# Conditional edges from execute_code
_graph.add_conditional_edges(
    "execute_code",
    route_after_execution,
    {
        "render_report": "render_report",
        "generate_code": "generate_code",
        "generate_plan": "generate_plan",
    },
)

# Terminal edge
_graph.add_edge("render_report", END)

# Compile once at module load
compiled_graph = _graph.compile()


@traceable(name="analysis_pipeline")
def run_pipeline(state: PipelineState) -> PipelineState:
    """Execute the full analysis pipeline via LangGraph.

    Entry point called from streamlit_app.py within @st.fragment.
    Returns the final PipelineState after the graph completes.

    LangSmith tracing is applied here only — individual nodes are
    traced automatically by LangGraph (NFR15: tracing is non-blocking).
    """
    try:
        result = compiled_graph.invoke(state)
        return result
    except Exception as e:
        # Surface error to state rather than crashing
        from utils.error_translation import translate_error
        error_msg = translate_error(e)
        return {**state, "execution_success": False, "error_messages": list(state.get("error_messages", [])) + [error_msg]}
```

**NOTE on `validate_code_node` → `execute_code` edge:** `validate_code_node` on failure sets `execution_success=False`. Since `execute_code` is always called next (linear edge), `execute_code` must NOT skip execution based on `execution_success` alone — it needs to run the subprocess regardless. The retry/replan routing happens AFTER `execute_code` completes. If `validate_code_node` fails, `execute_code` will still run the code (which will likely fail again), increment retry_count, and then route back to `generate_code` — which is fine since generate_code will regenerate with the error context. This is intentional behavior.

**ALTERNATIVE NOTE:** If you find that running `execute_code` after validation failure causes security issues (running invalid code in subprocess), add a guard at the top of `execute_code`:
```python
if state.get("validation_errors"):
    # Skip subprocess — validation already failed; increment retry and return
    new_retry = state.get("retry_count", 0) + 1
    return {
        "execution_success": False,
        "retry_count": new_retry,
        "replan_triggered": new_retry >= 3,
        "error_messages": state.get("error_messages", []),
    }
```
This is actually the SAFER approach and is recommended.

#### `pipeline/nodes/error_handler.py` — Implement Stub (not wired in graph)

Even though `handle_error` is not wired in the Approach A graph, the stub must be replaced with an implementation (it's a stub that raises NotImplementedError which would crash if accidentally called):

```python
def handle_error(state: PipelineState) -> dict:
    """Handle pipeline errors by incrementing retry count.

    Not currently wired as a graph node (Story 3.5 uses direct routing via
    route_after_execution). Implemented to complete the module stub.
    May be wired in future stories for more granular error handling.
    """
    current_retry = state.get("retry_count", 0)
    new_retry = current_retry + 1
    replan = new_retry >= 3
    existing_errors = list(state.get("error_messages", []))
    if replan:
        msg = "Maximum retries reached — adaptively replanning analysis approach."
    else:
        msg = f"Retrying code generation (attempt {new_retry}/3)."
    return {
        "retry_count": new_retry,
        "replan_triggered": replan,
        "error_messages": existing_errors + [msg],
    }
```

### Architecture Compliance Requirements

- **Module boundary:** `pipeline/graph.py` MUST NOT import `streamlit`
- **Module boundary:** `pipeline/nodes/error_handler.py` MUST NOT import `streamlit`
- **LangGraph node return:** All nodes return only changed keys — never `{**state, ...}` (exception: the `run_pipeline` catch-all uses spread because it's not a node)
- **Node function string names:** LangGraph node IDs must match function names exactly — e.g., `"validate_code_node"` (not `"validate_code"`)
- **`@traceable` placement:** Applied ONLY on `run_pipeline()` in `graph.py` — NEVER on individual node functions
- **LangSmith non-blocking:** Wrap `@traceable` import in try/except; if langsmith unavailable, fall back to identity decorator (NFR15)
- **Conditional edge map:** `graph.add_conditional_edges("execute_code", route_after_execution, {"render_report": "render_report", "generate_code": "generate_code", "generate_plan": "generate_plan"})` — exact match required for AC5
- **Error translation:** All errors routed through `translate_error()` from `utils/error_translation.py`

### Retry/Replan Logic Summary

| State | retry_count (after increment) | route_after_execution returns | replan_triggered |
|---|---|---|---|
| execution_success=True | unchanged (0–3) | "render_report" | False |
| execution_success=False, retry=0→1 | 1 | "generate_code" | False |
| execution_success=False, retry=1→2 | 2 | "generate_code" | False |
| execution_success=False, retry=2→3 | 3 | "generate_plan" | True |

`generate_code` already uses `state["retry_count"]` to include the last error in its prompt (Story 3.2) — no changes needed there.

`generate_plan` is re-invoked on the adaptive replan path with the accumulated `error_messages` and `replan_triggered=True` — the planner node may or may not use these fields currently, but having them in state is the contract.

### Testing Strategy

`tests/test_graph.py` should test graph structure and routing logic WITHOUT making real LLM API calls.

**Key test patterns:**

```python
# Test route_after_execution logic (pure function, no API calls)
from pipeline.graph import route_after_execution

def test_routes_to_render_on_success():
    state = {"execution_success": True, "retry_count": 0}
    assert route_after_execution(state) == "render_report"

def test_routes_to_generate_code_on_retry():
    state = {"execution_success": False, "retry_count": 1}
    assert route_after_execution(state) == "generate_code"

def test_routes_to_replan_on_max_retries():
    state = {"execution_success": False, "retry_count": 3}
    assert route_after_execution(state) == "generate_plan"

# Test graph importable and compiled
def test_compiled_graph_is_importable():
    from pipeline.graph import compiled_graph
    assert compiled_graph is not None

# Test no streamlit imports (ast.parse pattern)
def test_graph_no_streamlit_import():
    import ast, pathlib
    source = pathlib.Path("pipeline/graph.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                assert "streamlit" not in (name or ""), f"streamlit imported in graph.py: {name}"

# Test handle_error logic
def test_handle_error_increments_retry():
    from pipeline.nodes.error_handler import handle_error
    state = {"retry_count": 1, "replan_triggered": False, "error_messages": []}
    result = handle_error(state)
    assert result["retry_count"] == 2
    assert result["replan_triggered"] is False

def test_handle_error_triggers_replan_at_3():
    from pipeline.nodes.error_handler import handle_error
    state = {"retry_count": 2, "replan_triggered": False, "error_messages": []}
    result = handle_error(state)
    assert result["retry_count"] == 3
    assert result["replan_triggered"] is True
```

**Do NOT use real LLM calls in test_graph.py.** Test only:
- `route_after_execution` logic (pure function)
- `handle_error` logic (pure function)
- Import/module structure guards (ast.parse)
- `compiled_graph` existence and basic structure

### Previous Story Intelligence (from Story 3.4)

Key patterns and learnings:

- **Test count baseline:** 235 tests, 0 failures — MUST be preserved
- **LangGraph node return convention:** Only return changed keys — never `{**state, "key": value}` (except `run_pipeline` catch-all)
- **Error translation import path:** `from utils.error_translation import translate_error` — confirmed working
- **Module boundary guard test pattern:** `ast.parse()` on source file to check for streamlit imports — same pattern across all node tests
- **`error_messages` accumulation pattern:** `existing_errors = list(state.get("error_messages", [])); return {"error_messages": existing_errors + new_errors}` — preserve existing messages
- **Private helpers:** single underscore prefix (e.g., `_parse_stdout`)
- **executor.py existing tests:** 31 tests pass — modifying `execute_code` to add `retry_count` to return dict must NOT break these. The executor tests check return dict structure; adding new keys should be fine but verify `test_returns_only_changed_keys` and `test_does_not_spread_full_state` won't fail if those tests assert exact key sets.

### Git Intelligence

Recent commits (from `git log --oneline -8`):
- `b6352d31` — "Implemented epic-2" (most recent — note: possibly covers story 3.4 work too)
- `f1db0016` — "Implemented story 3-3-ast-allowlist-code-validator"
- `c44f5195` — "Implented epic-3 3-1, 3-2 and 3-3"
- `00618e91` — "Implemented epic-2"

**Files that MUST NOT be broken by Story 3.5:**
- `pipeline/nodes/intent.py` — no changes expected
- `pipeline/nodes/planner.py` — no changes expected
- `pipeline/nodes/codegen.py` — no changes expected
- `pipeline/nodes/validator.py` — no changes expected
- `utils/error_translation.py` — no changes (only imported)
- `utils/session.py` — no changes
- `streamlit_app.py` — no changes (Story 3.6 scope)
- All existing test files — do not modify, only add new `tests/test_graph.py`

**`pipeline/nodes/executor.py` modification:** Adding `retry_count` and `replan_triggered` to failure return paths is backwards-compatible. Verify `tests/test_executor.py` tests do not assert on exact key sets in a way that would fail when extra keys are added.

### Project Structure Notes

**Files to create/modify in Story 3.5:**
- `pipeline/graph.py` — replace `NotImplementedError` stub with full LangGraph StateGraph + `run_pipeline()`
- `pipeline/nodes/error_handler.py` — replace `NotImplementedError` stub with `handle_error()` implementation
- `pipeline/nodes/executor.py` — ADD `retry_count` and `replan_triggered` to failure return paths
- `tests/test_graph.py` — create new file with graph structure and routing tests

**No changes to:**
- `pipeline/nodes/validator.py` — Story 3.3 scope (done)
- `pipeline/nodes/reporter.py` — Story 3.6 scope (keep stub)
- `pipeline/nodes/codegen.py` — Story 3.2 scope (done; already has retry context)
- Any `utils/` file — no changes needed
- `streamlit_app.py` — no changes needed

### References

- Epic 3, Story 3.5 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-35-self-correcting-retry--adaptive-replan-loop]
- Architecture — LangGraph conditional edge routing (Gap 1): [Source: _bmad-output/planning-artifacts/architecture.md#architecture-validation-results]
- Architecture — `route_after_execution` exact specification: [Source: _bmad-output/planning-artifacts/architecture.md#architecture-validation-results]
- Architecture — `@traceable` placement pattern: [Source: _bmad-output/planning-artifacts/architecture.md#communication-patterns]
- Architecture — LangGraph node naming convention: [Source: _bmad-output/planning-artifacts/architecture.md#naming-patterns]
- Architecture — module boundaries: [Source: _bmad-output/planning-artifacts/architecture.md#architectural-boundaries]
- Architecture — internal data flow: [Source: _bmad-output/planning-artifacts/architecture.md#integration-points]
- Stub to implement: [pipeline/graph.py](pipeline/graph.py)
- Stub to implement: [pipeline/nodes/error_handler.py](pipeline/nodes/error_handler.py)
- Modify for retry_count: [pipeline/nodes/executor.py](pipeline/nodes/executor.py)
- Reference for graph node patterns: [pipeline/nodes/codegen.py](pipeline/nodes/codegen.py)
- Reference for routing test patterns: [tests/test_executor.py](tests/test_executor.py)
- Reference for module boundary test: [tests/test_validator.py](tests/test_validator.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `pipeline/graph.py` with full LangGraph `StateGraph`: all nodes registered, linear edges from `classify_intent` → `generate_plan` → `generate_code` → `validate_code_node` → `execute_code`, conditional edges from `execute_code` via `route_after_execution`, and terminal edge `render_report` → `END`. Graph compiled once at module load.
- Implemented `route_after_execution(state) -> str` routing function: `execution_success=True` → `"render_report"`, `retry_count < 3` → `"generate_code"`, `retry_count >= 3` → `"generate_plan"`. Returns only string values — satisfies AC5 exactly.
- Implemented `run_pipeline()` with `@traceable(name="analysis_pipeline")` (LangSmith, non-blocking). `@traceable` import wrapped in try/except for environments where langsmith is unavailable. Invocation wrapped in try/except to surface errors to state without crashing the UI layer.
- Implemented `handle_error()` in `pipeline/nodes/error_handler.py`: increments `retry_count`, sets `replan_triggered=True` at threshold (≥3), appends human-readable message to `error_messages`. Returns only changed keys. Not wired as a graph node in this story (Approach A chosen for AC5 compliance), but implemented to replace the NotImplementedError stub.
- Modified `pipeline/nodes/executor.py` (Story 3.5 additions): (1) Added validation guard at entry — if `validation_errors` is non-empty, skip subprocess, increment `retry_count`, return early. (2) Failure paths now also return `retry_count` (incremented) and `replan_triggered`. Success path unchanged to preserve Story 3.4 test assertions on exact key set.
- **Key design decision (Approach A)**: `retry_count` is incremented inside `execute_code` on failure paths (not by a separate `handle_error` node). This allows `route_after_execution` to return `"generate_code"` or `"generate_plan"` directly (satisfying AC5). The alternative (routing through `handle_error`) would violate the exact `add_conditional_edges` call required by AC5.
- **Validation guard rationale**: `validate_code_node` → `execute_code` is a linear edge per AC1. The guard in `execute_code` checks `validation_errors` (non-empty = validation failed) and short-circuits, preventing invalid code from reaching the subprocess sandbox.
- Created `tests/test_graph.py` with 25 tests across 4 test classes: `TestRouteAfterExecution` (8 routing logic tests), `TestHandleError` (10 pure-function tests), `TestGraphStructure` (6 structure/boundary tests), `TestConditionalEdgeSpec` (1 code inspection test). No LLM API calls in any test.
- Full regression suite: **260 tests, 0 failures** (235 pre-existing + 25 new). Zero regressions. All 31 existing executor tests pass with the executor modification.

### File List

- `pipeline/graph.py` — replaced NotImplementedError stub with full LangGraph StateGraph, `route_after_execution()` routing function with replan cap, and `run_pipeline()` with `@traceable`
- `pipeline/nodes/error_handler.py` — replaced NotImplementedError stub with `handle_error()` implementation (not wired in graph, replaces dangerous stub)
- `pipeline/nodes/executor.py` — added validation guard (skip subprocess on validation_errors, with context message) and `retry_count`/`replan_triggered` to failure return paths; success path unchanged
- `tests/test_graph.py` — new file: 27 tests for graph structure, routing logic (incl. replan cap), handle_error behavior, module boundary guards
- `tests/test_executor.py` — added 13 tests: validation guard (8) and failure path return structure (5)

### Change Log

- Implemented Story 3.5: Self-Correcting Retry & Adaptive Replan Loop (Date: 2026-03-11)
- Code review fixes applied (Date: 2026-03-11):
  - H1/H2: Added 13 tests to test_executor.py for validation guard (8 tests) and failure path return structure (5 tests)
  - H3: Added replan cap (_MAX_REPLAN_RETRY=6) in route_after_execution to prevent infinite loop; 3 new tests in test_graph.py
  - M1: Fixed story "IS NOT" section to accurately reflect executor.py changes
  - M2: Removed dead handle_error import from graph.py
  - M3: Added context message "Execution skipped — validation errors detected." to validation guard error_messages
  - Total: 275 tests, 0 failures (260 prior + 15 new from review fixes)
