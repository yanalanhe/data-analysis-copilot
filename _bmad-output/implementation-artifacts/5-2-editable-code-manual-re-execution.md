# Story 5.2: Editable Code & Manual Re-Execution

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want to edit the generated Python code directly in the Code tab and re-run it manually,
so that I can correct or extend the analysis without starting the entire workflow over.

## Acceptance Criteria

1. **Given** code is displayed in the Code tab editor, **When** I edit the code directly in the editor, **Then** my changes are reflected in the editor buffer in real time

2. **Given** I have edited the code, **When** I click a "Re-run" button in the Code tab, **Then** the modified code is sent through `validate_code_node()` and `execute_code()` — bypassing intent classification and plan generation

3. **Given** the re-run succeeds, **When** execution completes, **Then** new charts and trend analysis replace the previous report panel output

4. **Given** the re-run fails validation (unsafe operation or syntax error), **When** the validator catches it, **Then** a plain-English error message appears inline — no subprocess execution occurs and no raw traceback is shown

5. **Given** the re-run fails in the subprocess, **When** the error is caught, **Then** a translated error message appears in the report panel via `utils/error_translation.py`

## Tasks / Subtasks

- [x] Task 1: Update `col2row1_code_tab` block in `streamlit_app.py` to enable editing and re-execution (AC: #1, #2, #3, #4, #5)
  - [x] 1.1: Add two new imports at the top of `streamlit_app.py`:
    `from pipeline.nodes.validator import validate_code_node`
    `from pipeline.nodes.executor import execute_code`
  - [x] 1.2: Add a helper function `_build_reexec_state(ps: dict, edited_code: str) -> dict` in `streamlit_app.py` that builds a fresh execution state from the existing `pipeline_state` with the edited code — resets `validation_errors`, `retry_count`, `replan_triggered`, `execution_success`, `execution_output`, `error_messages`, `report_charts`, `report_text` to clean values while preserving `csv_temp_path`, `data_row_count`, `user_query`, `plan`, etc. from existing state
  - [x] 1.3: In the Code tab block (lines 1044–1063 of `streamlit_app.py`), when `generated_code` is non-empty:
    - Change `st_ace` from `readonly=True, key="code_viewer"` to `readonly=False, key="code_editor"` (AC #1)
    - Capture the return value: `edited_code = st_ace(...)` — `st_ace` returns the current editor content as a string (or `None` on initial render before user interaction)
    - Compute `current_code = edited_code if edited_code is not None else generated_code` to handle `None` on first render
  - [x] 1.4: Add a `st.button("Re-run", key="rerun_code")` below the `st_ace` editor within the code tab block (AC #2)
  - [x] 1.5: On Re-run button click — validation path (AC #4):
    - Build re-execution state: `re_exec_state = _build_reexec_state(ps, current_code)`
    - Call: `val_result = validate_code_node(re_exec_state)`
    - If `val_result.get("validation_errors")` is non-empty: display each message from `val_result.get("error_messages", [])` using `st.error(msg)` inline — **do NOT proceed to execution** — **do NOT call `st.rerun()`**
  - [x] 1.6: On Re-run button click — execution path (AC #2, #3, #5):
    - Only if `val_result.get("validation_errors")` is empty (validation passed):
    - Merge state: `merged_state = {**re_exec_state, **val_result}`
    - Call: `exec_result = execute_code(merged_state)`
    - Merge final: `final_state = {**merged_state, **exec_result}`
    - Persist: `st.session_state["pipeline_state"] = final_state`
    - Call: `st.rerun()` — this triggers `_execution_panel()` to re-render report with new `report_charts`/`report_text` (AC #3), or show error messages if execution failed (AC #5)

- [x] Task 2: Write tests in `tests/test_editable_code.py` (AC: #1, #2, #4, #5)
  - [x] 2.1: Test `_build_reexec_state()`: given a `pipeline_state` dict with various fields set, verify the returned dict has `generated_code` = edited_code, `retry_count` = 0, `validation_errors` = [], `error_messages` = [], `report_charts` = [], `report_text` = "", but preserves `csv_temp_path`, `user_query`, and `plan` from original
  - [x] 2.2: Test `_build_reexec_state()`: verify `execution_success` is `False` and `replan_triggered` is `False` regardless of original values
  - [x] 2.3: Test the re-execution validation gate: validate_code_node called with blocked import code → returns non-empty validation_errors → execution_must NOT be called; verified with direct function calls (AC #4)
  - [x] 2.4: Test re-execution success path: valid_code → validate_code_node passes → execute_code returns execution_success=True and report_text populated; verified with direct subprocess execution (AC #3)
  - [x] 2.5: Test re-execution failure path (subprocess error): AST-valid code that fails at runtime → execute_code returns execution_success=False, error_messages non-empty with translated strings, no raw tracebacks (AC #5)

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Changing the Code tab `st_ace` editor from `readonly=True` to `readonly=False` so the user can directly edit generated code
- Capturing the editor return value to get the current (possibly edited) code
- Adding a "Re-run" button that executes: validate → execute (bypassing all LLM nodes)
- Showing inline `st.error()` when validation fails (no subprocess, no raw traceback)
- Setting updated `pipeline_state` in `st.session_state` and calling `st.rerun()` on execution (success or failure), so `_execution_panel()` re-renders with new results or error messages

**IS NOT:**
- Running the full LangGraph pipeline (`run_pipeline()`) — the "Re-run" path calls `validate_code_node()` and `execute_code()` directly
- Adding a "Save as Template" button — that is Story 5.3
- Modifying `pipeline/`, `utils/`, or any file other than `streamlit_app.py` and a new test file
- Changing the Plan tab or Template tab — those are unaffected
- Auto-saving the edited code back to the original `generated_code` session state on every keystroke — only on "Re-run" button click

---

### Current Code Tab Block (Story 5.1 baseline — lines 1044–1063)

```python
with col2row1_code_tab:
    # Code tab: display generated code from pipeline_state
    # (sync: tests/test_code_viewer.py::get_code_for_display mirrors this logic)
    ps = st.session_state.get("pipeline_state")
    generated_code = (
        ps.get("generated_code", "")
        if isinstance(ps, dict)
        else ""
    )
    if generated_code:
        st_ace(
            value=generated_code,
            language="python",
            theme="monokai",
            readonly=True,
            height=400,
            key="code_viewer",
        )
    else:
        st.info("Run an analysis to see the generated code here")
```

**Target state after Story 5.2:**

```python
with col2row1_code_tab:
    # Code tab: editable code + manual re-execution (Story 5.2)
    # (sync: tests/test_code_viewer.py::get_code_for_display still valid for read path)
    ps = st.session_state.get("pipeline_state")
    generated_code = (
        ps.get("generated_code", "")
        if isinstance(ps, dict)
        else ""
    )
    if generated_code:
        edited_code = st_ace(
            value=generated_code,
            language="python",
            theme="monokai",
            readonly=False,
            height=400,
            key="code_editor",
        )
        # st_ace returns None on initial render before user interaction
        current_code = edited_code if edited_code is not None else generated_code

        if st.button("Re-run", key="rerun_code"):
            re_exec_state = _build_reexec_state(ps, current_code)
            val_result = validate_code_node(re_exec_state)

            if val_result.get("validation_errors"):
                # Validation failed — show inline, do NOT execute (AC #4)
                for msg in val_result.get("error_messages", []):
                    st.error(msg)
            else:
                # Validation passed — execute directly, bypassing LLM nodes (AC #2)
                merged_state = {**re_exec_state, **val_result}
                exec_result = execute_code(merged_state)
                final_state = {**merged_state, **exec_result}
                st.session_state["pipeline_state"] = final_state
                st.rerun()  # _execution_panel() re-renders with new results (AC #3, #5)
    else:
        st.info("Run an analysis to see the generated code here")
```

**Helper function to add in `streamlit_app.py` (near other helpers):**

```python
def _build_reexec_state(ps: dict, edited_code: str) -> dict:
    """Build a clean re-execution state from existing pipeline state with edited code.

    Preserves: user_query, csv_temp_path, data_row_count, intent, plan,
               large_data_detected, large_data_message, recovery_applied.
    Resets: generated_code (→ edited_code), validation_errors, retry_count,
            replan_triggered, execution_success, execution_output,
            error_messages, report_charts, report_text.
    """
    return {
        **ps,
        "generated_code": edited_code,
        "validation_errors": [],
        "retry_count": 0,
        "replan_triggered": False,
        "execution_success": False,
        "execution_output": "",
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
    }
```

---

### Key File Locations

| File | Lines | Purpose |
|---|---|---|
| `streamlit_app.py` | top imports | Add `from pipeline.nodes.validator import validate_code_node` and `from pipeline.nodes.executor import execute_code` |
| `streamlit_app.py` | near other helpers | Add `_build_reexec_state(ps, edited_code)` helper function |
| `streamlit_app.py` | ~1044–1063 | Code tab block — replace `st_ace` + add Re-run button + re-execution logic |
| `pipeline/nodes/validator.py` | `validate_code_node()` | Takes full `PipelineState` dict, returns `{"validation_errors": [...], "error_messages": [...]}` or `{"validation_errors": []}` — already handles translation |
| `pipeline/nodes/executor.py` | `execute_code()` | Takes full `PipelineState` dict, runs subprocess, returns partial dict with `report_charts`, `report_text`, `execution_success`, `error_messages` |
| `tests/test_editable_code.py` | new file | Unit tests for `_build_reexec_state` and re-execution logic |

---

### Architecture Compliance

- **Bypass LLM nodes:** The "Re-run" path calls `validate_code_node()` and `execute_code()` directly — this is valid because both functions operate on the `PipelineState` dict without depending on LangGraph graph wiring. `validate_code_node` only needs `state["generated_code"]`, and `execute_code` only needs `generated_code` + `csv_temp_path`. [Source: _bmad-output/planning-artifacts/architecture.md#requirements-to-structure-mapping]
- **Error translation:** All errors shown to the user go through `translate_error()` — `validate_code_node()` already calls `translate_error()` internally and returns translated messages in `error_messages`. `execute_code()` similarly calls `translate_error()` for subprocess errors. **Never display `repr(exception)` or raw tracebacks.** [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- **Tab state preservation:** After `st.rerun()`, the Code tab will re-initialize `st_ace` with `value=generated_code` from `pipeline_state` — at this point `pipeline_state["generated_code"]` equals the edited code (set in `_build_reexec_state`), so the editor retains the user's edited code. [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- **`st_ace` key change:** Story 5.1 used `key="code_viewer"` (read-only viewer). Story 5.2 changes to `key="code_editor"` (editable). Streamlit requires stable widget keys per run — changing the key from 5.1 is intentional: the editor is now a different widget (editable vs read-only). This will cause a one-time widget reset for users upgrading from 5.1 baseline, which is acceptable.
- **`_execution_panel()` re-render:** After `st.rerun()`, `_execution_panel()` (the `@st.fragment` function) renders the report from `st.session_state["pipeline_state"]["report_charts"]` and `["report_text"]`. It checks `pipeline_running` flag: since we do NOT set `pipeline_running=True`, the panel will NOT re-invoke the full pipeline — it just re-renders the stored state. This is the correct behavior. [Source: _bmad-output/planning-artifacts/architecture.md#Frontend-Architecture]
- **Module boundary:** Changes are entirely in `streamlit_app.py` (UI layer). `pipeline/` and `utils/` files are imported but not modified. [Source: _bmad-output/planning-artifacts/architecture.md#Architectural-Boundaries]

---

### `validate_code_node` and `execute_code` — Key Behaviors to Know

**`validate_code_node(state)`** (`pipeline/nodes/validator.py`):
- Reads `state["generated_code"]`
- Calls `validate_code(code)` → AST parse, checks ALLOWED_IMPORTS, BLOCKED_CALLS, BLOCKED_NAMESPACES
- If **invalid**: returns `{"validation_errors": [...raw_errors...], "execution_success": False, "error_messages": state["error_messages"] + [translated_errors...]}`
- If **valid**: returns `{"validation_errors": []}` — no `execution_success` key in this case
- Allowed imports: `pandas`, `numpy`, `matplotlib`, `matplotlib.pyplot`, `math`, `statistics`, `datetime`, `collections`, `itertools`, `io`, `base64`
- Blocked calls: `eval`, `exec`, `__import__`, `open`
- Blocked namespaces: `os`, `sys`, `subprocess`, `socket`, `urllib`, `requests`

**`execute_code(state)`** (`pipeline/nodes/executor.py`):
- Reads `state["generated_code"]` — writes to temp `analysis.py`
- Reads `state["csv_temp_path"]` — copies to temp `data.csv` if exists
- Runs in isolated subprocess with 60-second timeout and restricted env
- Parses `CHART:` prefix lines from stdout as base64-encoded PNG bytes
- If **success**: returns `{"report_charts": [...], "report_text": "...", "execution_output": "...", "execution_success": True, "error_messages": [...]}`
- If **failure**: returns `{"execution_success": False, "retry_count": old+1, "replan_triggered": new_retry>=3, "error_messages": [...translated...]}`
- **IMPORTANT:** `execute_code` checks `state["validation_errors"]` — if non-empty, it skips execution. Since we call `validate_code_node` first and only proceed when `validation_errors` is empty, this guard will never fire in the re-execution path.

---

### Session State Schema Reference

```python
# st.session_state["pipeline_state"] is a PipelineState TypedDict (or None before first run)
class PipelineState(TypedDict):
    user_query: str
    csv_temp_path: str           # Path to uploaded CSV in temp dir — PRESERVE in reexec
    data_row_count: int          # PRESERVE in reexec
    intent: Literal["report", "qa", "chat"]   # PRESERVE
    plan: list[str]              # PRESERVE
    generated_code: str          # OVERRIDE with edited_code in reexec
    validation_errors: list[str] # RESET to [] in reexec
    execution_output: str        # RESET to "" in reexec
    execution_success: bool      # RESET to False in reexec
    retry_count: int             # RESET to 0 in reexec
    replan_triggered: bool       # RESET to False in reexec
    error_messages: list[str]    # RESET to [] in reexec
    report_charts: list[bytes]   # RESET to [] in reexec (populated by execute_code on success)
    report_text: str             # RESET to "" in reexec (populated by execute_code on success)
    large_data_detected: bool    # PRESERVE
    large_data_message: str      # PRESERVE
    recovery_applied: str        # PRESERVE
```

---

### Previous Story Intelligence (from Story 5.1)

- **Story 5.1 baseline:** Code tab reads `pipeline_state["generated_code"]` from `st.session_state`. Uses `isinstance(ps, dict)` guard (not `is None` check) per code-review fix. `height=400` was added for AC#4 (viewport sizing). Test count after 5.1: 323 passing (316 baseline + 7 new from `test_code_viewer.py`).
- **Key pattern:** `st_ace` returns `None` on first render (before user interaction), then returns the editor content as a string on subsequent renders. Always handle `None` return: `current_code = edited_code if edited_code is not None else generated_code`.
- **Test approach:** Story 5.1 extracted `get_code_for_display()` helper in `test_code_viewer.py` and tested it in isolation without importing Streamlit. For Story 5.2, extract `_build_reexec_state()` as a standalone helper and test it directly. Mock `validate_code_node` and `execute_code` for integration-logic tests.
- **`isinstance(ps, dict)` guard:** Code review in 5.1 established that the guard against non-dict `pipeline_state` should use `isinstance(ps, dict)` not `ps is not None`. Follow this pattern in any new session-state reads.
- **`st_ace` key distinction:** 5.1 used `key="code_viewer"`. 5.2 must use `key="code_editor"` (different key = different widget identity in Streamlit's internal registry).

---

### Git Context (Recent Work)

Last 5 commits (Story 5.1 was implemented but not yet committed — changes are in working tree):
```
8a56ca40 Implemented epic-4 Large Data Resilience
60e038e0 Implemented story 3-6-non-blocking-execution-panel-visual-report-rendering
b6352d31 Implemented epic-2
f1db0016 Implemented story 3-3-ast-allowlist-code-validator
c44f5195 Implented epic-3 3-1, 3-2 and 3-3
```

**Story 5.1 working-tree changes (not yet committed):**
- `streamlit_app.py` — Code tab block at lines 1044–1063 replaced (Story 5.1 is DONE)
- `tests/test_code_viewer.py` — new file (6 unit tests, all passing)
- Total: 323 tests passing

Story 5.2 builds directly on Story 5.1's implementation. The baseline `streamlit_app.py` for Story 5.2 is the **post-5.1 modified version** (not the last commit). Verify the current Code tab matches the Story 5.1 "target state" before starting Story 5.2.

---

### References

- Story 5.2 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-52-editable-code-manual-re-execution]
- Story 5.1 baseline (Code tab): [Source: _bmad-output/implementation-artifacts/5-1-code-viewer-in-streamlit-ace-editor.md]
- `validate_code_node` and `execute_code`: [Source: pipeline/nodes/validator.py, pipeline/nodes/executor.py]
- Error translation requirement: [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- `PipelineState` schema: [Source: _bmad-output/planning-artifacts/architecture.md#data-architecture]
- Tab state preservation: [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- Architecture boundary (FR24 → `streamlit_app.py` Code tab): [Source: _bmad-output/planning-artifacts/architecture.md#requirements-to-structure-mapping]
- `_execution_panel()` re-render behavior: [Source: _bmad-output/planning-artifacts/architecture.md#Frontend-Architecture]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_No debug issues encountered._

### Completion Notes List

- Added `from pipeline.nodes.validator import validate_code_node` and `from pipeline.nodes.executor import execute_code` imports to `streamlit_app.py`.
- Added `_build_reexec_state(ps, edited_code)` helper function after `_make_initial_pipeline_state()` — resets all execution fields (generated_code, validation_errors, retry_count, replan_triggered, execution_success, execution_output, error_messages, report_charts, report_text) while preserving context fields (csv_temp_path, user_query, plan, intent, data_row_count, large_data_*).
- Updated Code tab block in `streamlit_app.py` (lines ~1071–1108): changed `st_ace` from `readonly=True, key="code_viewer"` to `readonly=False, key="code_editor"`, captured return value with `None` guard, added "Re-run" button with full validate→execute flow.
- Re-run path calls `validate_code_node()` then `execute_code()` directly — bypasses all LLM nodes (intent/plan/codegen). Validation failures display inline via `st.error()` without calling `st.rerun()`. Execution results (success or failure) stored in `st.session_state["pipeline_state"]` and `st.rerun()` triggers `_execution_panel()` re-render.
- 20 new unit tests added in `tests/test_editable_code.py` covering: `_build_reexec_state` field preservation (9 tests), reset correctness (3 tests), validation gate (3 tests), success path (3 tests), failure path (2 tests).
- Full regression suite: 342 passed (322 baseline + 20 new), 0 failures.

### File List

- `streamlit_app.py` (modified — added 2 imports, added `_build_reexec_state()` helper, replaced Code tab block with editable editor + Re-run button + re-execution logic)
- `utils/reexec.py` (new — extracted `build_reexec_state()` from streamlit_app.py for testability, with explicit key preservation and None guard)
- `tests/test_editable_code.py` (new — 22 unit tests for re-execution state building and flow logic)

### Change Log

- 2026-03-12: Story 5.2 implemented — Code tab upgraded from read-only viewer to editable editor with manual Re-run; added `_build_reexec_state()` helper and validate→execute re-execution path bypassing LLM nodes. 20 new tests, 342 total passing.
- 2026-03-13: Code review fixes (claude-opus-4-6) — [H1] Added st.spinner around Re-run execution path; [H2] Extracted build_reexec_state to utils/reexec.py so tests import production code directly (eliminated mirrored copy); [M1] Added None edited_code fallback + test; [M2] Clear stale report on validation failure; [M3] Explicit _PRESERVED_KEYS instead of **ps spread + test. 344 total passing (2 new edge case tests).
