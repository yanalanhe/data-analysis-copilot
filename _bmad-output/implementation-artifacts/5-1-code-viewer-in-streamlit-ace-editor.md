# Story 5.1: Code Viewer in streamlit-ace Editor

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want to view the Python code generated for any analysis in the Code tab,
so that I can inspect what the system did and build trust in the output.

## Acceptance Criteria

1. **Given** a completed analysis, **When** I click the Code tab, **Then** the generated Python code from `pipeline_state["generated_code"]` is displayed in a `streamlit-ace` Monaco editor

2. **Given** the Code tab, **When** I switch to it from the Plan tab and back again, **Then** the code content is preserved without re-generating — it reads from session state, not a fresh LLM call

3. **Given** no analysis has been run yet, **When** I click the Code tab, **Then** the editor shows a placeholder message: "Run an analysis to see the generated code here"

4. **Given** the Code tab is visible, **When** I view it at any screen width >= 1280px, **Then** the editor is fully visible without horizontal scrolling and syntax is highlighted

## Tasks / Subtasks

- [x] Task 1: Update `col2row1_code_tab` block in `streamlit_app.py` to display new pipeline's generated code (AC: #1, #2, #3, #4)
  - [x] 1.1: Read `pipeline_state["generated_code"]` from `st.session_state.get("pipeline_state")` — use `.get("generated_code", "")` to safely access the field
  - [x] 1.2: When `generated_code` is non-empty: render it in `st_ace(value=generated_code, language="python", theme="monokai", readonly=True, key="code_viewer")` — `readonly=True` because editing is Story 5.2
  - [x] 1.3: When `generated_code` is empty or `pipeline_state` is `None`: display `st.info("Run an analysis to see the generated code here")` as placeholder
  - [x] 1.4: Remove legacy `st.write(session_state_auto.formatted_output)` and `st.write("### Code For Visualizing Report")` lines from the Code tab block — these show brownfield pipeline output and are no longer needed in this tab
  - [x] 1.5: Remove legacy `st.session_state.code = reporting_code` write-back (line ~1051) from the Code tab block — this stored the editor value back to `st.session_state.code` which is a brownfield field; the new Code tab reads from `pipeline_state` in session state only
  - [x] 1.6: The `st_ace` key must be `"code_viewer"` (distinct from any future `"code_editor"` key used in Story 5.2 for the editable variant)

- [x] Task 2: Write tests in `tests/test_code_viewer.py` for the Code tab logic (AC: #1, #2, #3)
  - [x] 2.1: Test helper: extract the `get_code_for_display()` logic (or equivalent) if it gets factored out — otherwise test via session state reading pattern
  - [x] 2.2: Test: `pipeline_state` is `None` → `generated_code` resolves to `""` → placeholder path taken
  - [x] 2.3: Test: `pipeline_state` is `{}` (dict with no `generated_code` key) → `generated_code` resolves to `""` → placeholder path taken
  - [x] 2.4: Test: `pipeline_state["generated_code"]` is `""` (empty string) → placeholder path taken
  - [x] 2.5: Test: `pipeline_state["generated_code"]` contains valid Python code → non-empty string is returned for display

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Replacing the Code tab block (lines ~1044–1051 in `streamlit_app.py`) so it reads from `pipeline_state["generated_code"]` instead of the legacy `st.session_state.code`
- Showing the `streamlit-ace` Monaco editor in read-only mode when code is available
- Showing a placeholder `st.info()` when no analysis has run
- Removing legacy brownfield `session_state_auto.formatted_output` and `st.session_state.code` writes from the Code tab

**IS NOT:**
- Adding an "Edit" capability or "Re-run" button — that is Story 5.2
- Adding a "Save as Template" button — that is Story 5.3
- Modifying `pipeline/`, `utils/`, or any file other than `streamlit_app.py` and a new test file
- Changing the Plan tab or Template tab — those are unaffected

---

### Current Code Tab State (Brownfield Baseline)

The current Code tab (lines 1044–1051 of `streamlit_app.py`) is:

```python
with col2row1_code_tab:
    st.write(session_state_auto.formatted_output)
    st.write("### Code For Visualizing Report")
    reporting_code = st_ace(
        value=st.session_state.code, language="python", theme="monokai"
    )
    if reporting_code:
        st.session_state.code = reporting_code
```

This reads from the **legacy brownfield** `st.session_state.code` and `session_state_auto.formatted_output`. These are set by the old `lg_write_code`/`lg_check_code` LangGraph nodes that are no longer the execution path.

The new pipeline stores generated code in `st.session_state["pipeline_state"]["generated_code"]` (set by `pipeline/nodes/codegen.py`).

**Target state after Story 5.1:**

```python
with col2row1_code_tab:
    ps = st.session_state.get("pipeline_state")
    generated_code = ps.get("generated_code", "") if ps else ""
    if generated_code:
        st_ace(
            value=generated_code,
            language="python",
            theme="monokai",
            readonly=True,
            key="code_viewer",
        )
    else:
        st.info("Run an analysis to see the generated code here")
```

### Key File Locations

| File | Lines | Purpose |
|---|---|---|
| `streamlit_app.py` | ~1044–1051 | Code tab block — replace entire content |
| `streamlit_app.py` | line 20 | `from streamlit_ace import st_ace` — already imported, no change |
| `pipeline/nodes/codegen.py` | whole file | Sets `pipeline_state["generated_code"]` — read-only dependency |
| `pipeline/state.py` | `generated_code: str` field | TypedDict field to read from |
| `tests/test_code_viewer.py` | new file | Unit tests for code display logic |

### Architecture Compliance

- **Tab state preservation:** The Code tab reads `pipeline_state["generated_code"]` from `st.session_state` — switching tabs never re-triggers an LLM call. Content is preserved across tab switches because `pipeline_state` persists in `st.session_state` throughout the session. [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- **`streamlit-ace` version:** `streamlit-ace 0.1.1` is already in `requirements.txt` and already imported at line 20. No version change needed. [Source: _bmad-output/planning-artifacts/architecture.md#Existing-Technology-Baseline]
- **Module boundary:** The change is entirely in `streamlit_app.py` (UI layer). No `pipeline/` or `utils/` files are modified. [Source: _bmad-output/planning-artifacts/architecture.md#Architectural-Boundaries]
- **`readonly=True`:** Story 5.1 is a viewer only. The `st_ace` `readonly=True` parameter disables editing. Story 5.2 will add an editable variant with a distinct key `"code_editor"`.
- **`key="code_viewer"`:** Streamlit requires stable widget keys. Using `"code_viewer"` avoids conflicts with Story 5.2's future `"code_editor"` key.

### Session State Schema Reference

The `pipeline_state` is stored in `st.session_state["pipeline_state"]` as a `PipelineState` TypedDict (or `None` before first run). The `generated_code` field is:

```python
class PipelineState(TypedDict):
    ...
    generated_code: str   # set by pipeline/nodes/codegen.py after LLM call
    ...
```

`pipeline_state` is written by the `@st.fragment` execution panel in `_execution_panel()` after `run_pipeline()` completes:
```python
st.session_state["pipeline_state"] = result
```
[Source: _bmad-output/planning-artifacts/architecture.md#data-architecture, _bmad-output/planning-artifacts/architecture.md#Frontend-Architecture]

### Previous Story Intelligence (from Story 4.2)

- **Test pattern:** New test classes are added as separate files (`tests/test_large_data.py`, etc.). Use `tests/test_code_viewer.py` as the new test file.
- **Test count baseline:** 316 tests collected after Story 4.2. Expect at least 4 new tests.
- **Import pattern in tests:** Story 4.2 used `import` inside test methods for lazy loading. For `streamlit_app.py` code testing, unit-test the pure logic (session state reading) rather than trying to import the Streamlit app — mock `st.session_state` or extract testable helpers.
- **`_execution_panel()`** is the `@st.fragment`-decorated panel in `streamlit_app.py` that sets `st.session_state["pipeline_state"]`. The Code tab reads from this same session state.
- **Brownfield coexistence:** The legacy `st.session_state.code` field (dot-access) is set by lines ~768 and ~871 in `streamlit_app.py` (old LangGraph pipeline). Story 5.1 removes the write-back from the Code tab but does NOT touch those legacy setters — they may still be used by legacy paths that are being phased out.

### Git Context (Recent Work)

Last 5 commits show Epic 4 was just completed:
```
8a56ca40 Implemented epic-4 Large Data Resilience
60e038e0 Implemented story 3-6-non-blocking-execution-panel-visual-report-rendering
b6352d31 Implemented epic-2
f1db0016 Implemented story 3-3-ast-allowlist-code-validator
c44f5195 Implented epic-3 3-1, 3-2 and 3-3
```

The execution panel (`_execution_panel()` with `@st.fragment`), the full pipeline (`run_pipeline()`), and the `pipeline_state` session key are all fully implemented and working.

### References

- Story 5.1 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-51-code-viewer-in-streamlit-ace-editor]
- `streamlit-ace` in tech stack: [Source: _bmad-output/planning-artifacts/architecture.md#Existing-Technology-Baseline]
- Code Transparency FR mapping: [Source: _bmad-output/planning-artifacts/epics.md#fr-coverage-map] (FR23 → Epic 5, "Code viewer")
- Tab state preservation requirement: [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- Architecture boundary (FR23–25 → `streamlit_app.py` Code tab): [Source: _bmad-output/planning-artifacts/architecture.md#requirements-to-structure-mapping]
- `pipeline_state` session state schema: [Source: _bmad-output/planning-artifacts/architecture.md#data-architecture]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_No debug issues encountered._

### Completion Notes List

- Replaced legacy Code tab block (lines 1044–1051) in `streamlit_app.py` with new pipeline-reading implementation.
- New block reads `pipeline_state["generated_code"]` from `st.session_state` via `.get()` safe-access pattern.
- `st_ace` rendered as read-only (`readonly=True`, `key="code_viewer"`) when code is present; `st.info` placeholder shown otherwise.
- All legacy brownfield lines removed: `session_state_auto.formatted_output`, `st.write("### Code For Visualizing Report")`, old `st_ace` call using `st.session_state.code`, and write-back `st.session_state.code = reporting_code`.
- 7 new unit tests added in `tests/test_code_viewer.py` covering all AC #1/#2/#3 scenarios.
- Full regression suite: 323 passed (316 baseline + 7 new), 0 failures.

### File List

- `streamlit_app.py` (modified — Code tab block lines 1044–1051 replaced)
- `tests/test_code_viewer.py` (new — 6 unit tests for code display logic)

### Change Log

- 2026-03-12: Story 5.1 implemented — replaced legacy Code tab with pipeline_state-reading st_ace viewer (readonly), added placeholder, removed brownfield writes. 7 new tests, 323 total passing.
- 2026-03-12: Code review fixes applied — (1) aligned test helper with inline logic using `isinstance(ps, dict)` guard instead of `is None` check, added sync comments; (2) added `height=400` to st_ace for proper viewport sizing (AC#4); (3) removed 2 redundant tests, added non-dict edge-case test (6 tests total); (4) added `isinstance` type guard in streamlit_app.py for robustness.
