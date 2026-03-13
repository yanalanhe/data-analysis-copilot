# Story 4.1: Large Dataset Detection & Inline Warning

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want to see a clear inline message immediately when I upload a dataset that exceeds the visualization threshold,
so that I know what's happening before any analysis runs and can decide what to do.

## Acceptance Criteria

1. **Given** I upload CSV files with combined row count >= 100,000 OR combined size >= 20MB, **When** the upload handler in `streamlit_app.py` processes the files, **Then** `detect_large_data()` from `utils/large_data.py` is called and returns `True`

2. **Given** large data is detected, **When** I view the report panel (bottom-right), **Then** an inline message appears — no modal or popup — stating: "Your dataset has X rows / Y MB, which exceeds the visualization threshold."

3. **Given** CSV files with combined row count < 100,000 AND combined size < 20MB, **When** I upload them, **Then** no warning is shown and the session proceeds normally with no degraded-path flag set

4. **Given** large data detection, **When** the check runs, **Then** it executes on CSV upload — before any pipeline execution attempt (NFR5)

5. **Given** the detection check running on upload, **When** I view the UI, **Then** it remains fully responsive — no blocking or freezing during detection (NFR5)

## Tasks / Subtasks

- [x] Task 1: Implement `detect_large_data()` in `utils/large_data.py` (AC: #1, #3)
  - [x] 1.1: Replace the `# TODO: implement in Story 4.1` stub with real threshold logic
  - [x] 1.2: Return `True` when `row_count >= LARGE_DATA_ROW_THRESHOLD` OR `size_mb >= LARGE_DATA_SIZE_THRESHOLD_MB`
  - [x] 1.3: Return `False` for all values below both thresholds
  - [x] 1.4: Do NOT import streamlit — pure utility function (module boundary rule)
  - [x] 1.5: Constants are already defined: `LARGE_DATA_ROW_THRESHOLD = 100_000`, `LARGE_DATA_SIZE_THRESHOLD_MB = 20.0` — use them

- [x] Task 2: Update `_on_csv_upload()` in `streamlit_app.py` to store detection result in session state (AC: #1, #2, #3, #4)
  - [x] 2.1: Use the return value from `detect_large_data(len(combined_df), combined_size_mb)` — currently called but ignored
  - [x] 2.2: If `detect_large_data()` returns `True`: set `st.session_state["large_data_detected"] = True` and `st.session_state["large_data_message"]` = formatted message with actual row count and MB value
  - [x] 2.3: If `detect_large_data()` returns `False`: set `st.session_state["large_data_detected"] = False` and `st.session_state["large_data_message"] = ""`
  - [x] 2.4: Format the message exactly as: `f"Your dataset has {row_count:,} rows / {size_mb:.1f} MB, which exceeds the visualization threshold."` (use Python f-string with comma formatting for row count and 1 decimal for MB)
  - [x] 2.5: Detection runs AFTER the temp CSV is written — detection is read-only; it does NOT change the data or temp file (downsampling is Story 4.2 scope)

- [x] Task 3: Add `large_data_detected` and `large_data_message` defaults to `init_session_state()` in `utils/session.py` (AC: #3)
  - [x] 3.1: Add `"large_data_detected": False` to the `defaults` dict in `init_session_state()`
  - [x] 3.2: Add `"large_data_message": ""` to the `defaults` dict in `init_session_state()`
  - [x] 3.3: Idempotent — only sets key if not already present (consistent with existing pattern)
  - [x] 3.4: This ensures the keys exist on first load before any CSV is uploaded — prevents `KeyError` on `_execution_panel()` and `_make_initial_pipeline_state()`

- [x] Task 4: Show inline large data warning in `_execution_panel()` in `streamlit_app.py` (AC: #2, #5)
  - [x] 4.1: At the TOP of `_execution_panel()`, after `st.write("### AI Generated Report")`, add a check for `st.session_state.get("large_data_detected")`
  - [x] 4.2: If `large_data_detected` is `True`, display the message using `st.warning(st.session_state.get("large_data_message", ""))` — inline, no modal, always visible in the report panel
  - [x] 4.3: The warning must appear regardless of whether the pipeline is running, has run, or has not run yet — it reflects the upload state, not execution state
  - [x] 4.4: When `large_data_detected` is `False` (or not set), display nothing — no change to current behaviour
  - [x] 4.5: Do NOT use `st.error()` for the large data warning — use `st.warning()` (it's a caution, not an error)

- [x] Task 5: Write tests in `tests/test_large_data.py` (AC: #1, #2, #3)
  - [x] 5.1: Test `detect_large_data(100_000, 5.0)` returns `True` (row threshold hit)
  - [x] 5.2: Test `detect_large_data(99_999, 5.0)` returns `False` (below both thresholds)
  - [x] 5.3: Test `detect_large_data(50_000, 20.0)` returns `True` (MB threshold hit)
  - [x] 5.4: Test `detect_large_data(50_000, 19.9)` returns `False` (below both thresholds)
  - [x] 5.5: Test `detect_large_data(0, 0.0)` returns `False` (empty dataset is not large)
  - [x] 5.6: Test `detect_large_data(200_000, 50.0)` returns `True` (both thresholds exceeded)
  - [x] 5.7: Test `detect_large_data(100_001, 0.1)` returns `True` (only row threshold exceeded)
  - [x] 5.8: Test `large_data.py` does NOT import streamlit — use `ast.parse()` pattern (same as other utility tests)
  - [x] 5.9: Test that `LARGE_DATA_ROW_THRESHOLD`, `LARGE_DATA_SIZE_THRESHOLD_MB`, `DOWNSAMPLE_TARGET_ROWS` constants are importable and have correct values (`100_000`, `20.0`, `10_000`)
  - [x] 5.10: Test boundary condition: `detect_large_data(100_000, 0.1)` returns `True` (exactly at row threshold — >= not >)
  - [x] 5.11: Test boundary condition: `detect_large_data(1, 20.0)` returns `True` (exactly at MB threshold)

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing `detect_large_data()` in `utils/large_data.py` with real threshold logic (replacing `return False` stub)
- Updating `_on_csv_upload()` in `streamlit_app.py` to use the return value and set session state
- Adding `large_data_detected` and `large_data_message` defaults to `init_session_state()` in `utils/session.py`
- Displaying the inline warning in `_execution_panel()` in the report panel (bottom-right)
- Writing unit tests in `tests/test_large_data.py`

**IS NOT:**
- Implementing `apply_uniform_stride()` or auto-downsampling (Story 4.2 scope)
- Adding the "Auto-downsample to 10,000 points" button (Story 4.2 scope)
- Showing the downsampling note alongside charts (Story 4.2 scope)
- Modifying `PipelineState` fields (already defined with `large_data_detected`, `large_data_message`, `recovery_applied` — no changes needed)
- Modifying any pipeline node (this is a UI-layer and utils story only)
- Changing how the combined CSV is written to the temp file (detection is read-only in 4.1)

### Current State of `utils/large_data.py` (Stubs to Replace)

```python
# Current — STUB (needs replacing in Task 1):
def detect_large_data(row_count: int, size_mb: float) -> bool:
    # TODO: implement in Story 4.1
    return False  # ← REPLACE THIS

# Current — STUB (Story 4.2 scope — DO NOT TOUCH in 4.1):
def apply_uniform_stride(df: pd.DataFrame, target_rows: int = DOWNSAMPLE_TARGET_ROWS) -> pd.DataFrame:
    # TODO: implement in Story 4.2
    return df  # ← Leave as-is
```

**Correct implementation (Task 1):**
```python
def detect_large_data(row_count: int, size_mb: float) -> bool:
    """Return True if dataset exceeds the visualization size thresholds.

    Thresholds: >= 100,000 rows OR >= 20 MB combined size.
    Called on CSV upload before any pipeline execution (NFR5).
    """
    return row_count >= LARGE_DATA_ROW_THRESHOLD or size_mb >= LARGE_DATA_SIZE_THRESHOLD_MB
```

### Current State of `_on_csv_upload()` in `streamlit_app.py`

The existing code at lines 155-157:
```python
# Hook for large data detection — stub returns False until Story 4.1
combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
detect_large_data(len(combined_df), combined_size_mb)   # ← return value IGNORED
```

**Replace those 3 lines with (Task 2):**
```python
combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
row_count = len(combined_df)
is_large = detect_large_data(row_count, combined_size_mb)
if is_large:
    st.session_state["large_data_detected"] = True
    st.session_state["large_data_message"] = (
        f"Your dataset has {row_count:,} rows / {combined_size_mb:.1f} MB, "
        "which exceeds the visualization threshold."
    )
else:
    st.session_state["large_data_detected"] = False
    st.session_state["large_data_message"] = ""
```

**Note:** The `combined_size_mb` variable is already computed just above this block — no redundant calculation.

### Adding Defaults to `init_session_state()` (Task 3)

In `utils/session.py`, the current `defaults` dict is:
```python
defaults = {
    "uploaded_dfs": {},
    "csv_temp_path": None,
    "chat_history": [],
    "pipeline_state": None,
    "pipeline_running": False,
    "plan_approved": False,
    "active_tab": "plan",
    "active_template": None,
}
```

Add two new keys:
```python
defaults = {
    "uploaded_dfs": {},
    "csv_temp_path": None,
    "chat_history": [],
    "pipeline_state": None,
    "pipeline_running": False,
    "plan_approved": False,
    "active_tab": "plan",
    "active_template": None,
    "large_data_detected": False,    # ← NEW (Story 4.1)
    "large_data_message": "",         # ← NEW (Story 4.1)
}
```

**Why this matters:** `_make_initial_pipeline_state()` (streamlit_app.py line 181-182) already reads these with `.get()` fallbacks, but `_execution_panel()` will need them to always be present to avoid a `KeyError`. Adding to `init_session_state()` ensures they exist from the first app load before any CSV upload.

### Inline Warning in `_execution_panel()` (Task 4)

The `_execution_panel()` function in `streamlit_app.py` currently starts with:
```python
@st.fragment
def _execution_panel() -> None:
    """Execution panel — @st.fragment ensures only this panel reruns during pipeline execution."""
    st.write("### AI Generated Report")

    ps = st.session_state.get("pipeline_state")
    ...
```

**Add the large data warning after the heading (Task 4):**
```python
@st.fragment
def _execution_panel() -> None:
    """Execution panel — @st.fragment ensures only this panel reruns during pipeline execution."""
    st.write("### AI Generated Report")

    # Story 4.1: Show large data inline warning (no modal — UX spec requirement)
    if st.session_state.get("large_data_detected"):
        st.warning(st.session_state.get("large_data_message", ""))

    ps = st.session_state.get("pipeline_state")
    ...
```

**Key design decisions:**
- Use `st.warning()` not `st.error()` — it's informational, not a failure
- Place it BEFORE the pipeline running check — so it shows regardless of execution state
- It reflects upload state, not pipeline state — always shows when data is large

### Message Format (FR27)

Per architecture and AC:
```
"Your dataset has X rows / Y MB, which exceeds the visualization threshold."
```

Python format string with:
- Row count: `f"{row_count:,}"` — adds thousands separator for readability (e.g., `150,000`)
- Size MB: `f"{size_mb:.1f}"` — one decimal place (e.g., `23.5 MB`)

Example: `"Your dataset has 150,000 rows / 23.5 MB, which exceeds the visualization threshold."`

**Note:** Story 4.2 will extend this message or add a button below it. Story 4.1 only needs the detection and the warning text.

### Module Boundary Compliance

- `utils/large_data.py` — MUST NOT import streamlit ✅ (already clean; no streamlit in current stub)
- `utils/session.py` — CAN import streamlit (it's the permitted exception)
- `streamlit_app.py` — UI layer owns all `st.session_state` writes ✅
- Pipeline nodes — no changes needed (they receive `large_data_detected` via `PipelineState`, already handled in `_make_initial_pipeline_state()`)

### Architecture Compliance

- Detection runs on CSV upload (in `_on_csv_upload()`), NOT at execution time (NFR5) ✅
- Inline message in report panel, no modal (architecture: "Inline message in report panel (no modals — anti-pattern per UX spec)") ✅
- All exceptions handled within existing try/except in `_on_csv_upload()` — `detect_large_data()` is a pure comparison function that cannot throw ✅
- `detect_large_data()` is pure Python with no side effects — idempotent, testable, and safe to call on every upload ✅

### Project Structure Notes

**Files to create/modify in Story 4.1:**
- `utils/large_data.py` — replace `detect_large_data()` stub with real threshold comparison (leave `apply_uniform_stride()` stub alone)
- `utils/session.py` — add `large_data_detected: False` and `large_data_message: ""` to `defaults` dict
- `streamlit_app.py` — update `_on_csv_upload()` to use return value and set session state; update `_execution_panel()` to show inline warning
- `tests/test_large_data.py` — fill in the existing empty test file with threshold tests

**No changes to:**
- `pipeline/nodes/` — no changes (large_data_detected already flows through PipelineState)
- `pipeline/state.py` — already has `large_data_detected`, `large_data_message`, `recovery_applied` fields
- `pipeline/graph.py` — no changes
- Any existing test file (only filling in the already-stubbed `tests/test_large_data.py`)

### Previous Story Intelligence (from Story 3.6)

Key learnings from Story 3.6:
- **Test count:** 287 tests, 0 failures — must be preserved and extended
- **Module boundary guard test pattern:** `ast.parse()` on source file — use same pattern in test_large_data.py for the no-streamlit-import check
- **`st.warning()` for user-facing informational messages** — previously `st.error()` was used for errors; large data detection is a warning, not an error
- **`@st.fragment` behaviour:** When `_execution_panel()` is called on every page rerun (from col2row2), the new `st.warning()` check at the top of the fragment will also execute on every fragment rerun — this is correct behaviour since `large_data_detected` is in session_state which persists
- **Streamlit version:** 1.55.0 — `st.warning()`, `st.fragment`, and `st.status` are all available ✅

### Git Intelligence

Recent commits:
- `60e038e0` — Story 3.6: Non-Blocking Execution Panel & Visual Report Rendering (287 tests, 0 failures)
- `b6352d31` — Epic 2 implementation
- Previous: Epics 1, 2, 3 complete

**Files that MUST NOT be broken by Story 4.1:**
- `pipeline/nodes/executor.py` — no changes
- `pipeline/nodes/codegen.py` — no changes
- `pipeline/nodes/validator.py` — no changes
- `pipeline/nodes/reporter.py` — no changes
- `pipeline/graph.py` — no changes
- `utils/error_translation.py` — no changes
- All existing test files — do not modify (only fill in the empty `test_large_data.py`)

### References

- Epic 4, Story 4.1 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-41-large-dataset-detection--inline-warning]
- Architecture — large data process pattern: [Source: _bmad-output/planning-artifacts/architecture.md#process-patterns]
- Architecture — large data user message pattern: [Source: _bmad-output/planning-artifacts/architecture.md#frontend-architecture]
- Architecture — dual threshold constants: [Source: _bmad-output/planning-artifacts/architecture.md#implementation-patterns--consistency-rules]
- FR26, FR27: [Source: _bmad-output/planning-artifacts/epics.md#requirements-inventory]
- NFR5: "Dataset size detection and any resulting user message are surfaced immediately upon or before execution": [Source: _bmad-output/planning-artifacts/epics.md#nonfunctional-requirements]
- Utils stub to implement: [utils/large_data.py](utils/large_data.py)
- Upload handler to update: [streamlit_app.py](streamlit_app.py) (lines 155–157)
- Execution panel to update: [streamlit_app.py](streamlit_app.py) (`_execution_panel()` function)
- Session init to update: [utils/session.py](utils/session.py) (`init_session_state()` defaults dict)
- Empty test file to fill: [tests/test_large_data.py](tests/test_large_data.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `detect_large_data(row_count, size_mb)` in `utils/large_data.py` — replaced the `return False` stub with a one-line threshold comparison: `return row_count >= LARGE_DATA_ROW_THRESHOLD or size_mb >= LARGE_DATA_SIZE_THRESHOLD_MB`. Uses existing constants `LARGE_DATA_ROW_THRESHOLD = 100_000` and `LARGE_DATA_SIZE_THRESHOLD_MB = 20.0`. No streamlit import — pure utility function.
- Updated `_on_csv_upload()` in `streamlit_app.py` — the return value of `detect_large_data()` is now used. Sets `st.session_state["large_data_detected"]` (bool) and `st.session_state["large_data_message"]` (formatted string with comma-separated row count and 1-decimal MB) on every upload. Both values are reset to `False`/`""` when below threshold, ensuring correct behaviour on re-upload with smaller files.
- Added `"large_data_detected": False` and `"large_data_message": ""` to the `defaults` dict in `init_session_state()` in `utils/session.py`. Both keys are now initialized on every fresh app load before any CSV upload, preventing `KeyError` in `_execution_panel()`.
- Added inline large data warning to `_execution_panel()` in `streamlit_app.py` — placed immediately after the "### AI Generated Report" heading using `st.warning()` (not `st.error()`). The warning appears regardless of pipeline state; it's controlled entirely by `st.session_state["large_data_detected"]`. No modal — satisfies UX spec and architecture requirement.
- Filled `tests/test_large_data.py` with 17 tests across 4 classes: `TestConstants` (3), `TestDetectLargeDataRowThreshold` (4), `TestDetectLargeDataSizeThreshold` (4), `TestDetectLargeDataBothThresholds` (5), `TestLargeDataModuleBoundary` (1). Covers all 11 subtasks 5.1–5.11 plus boundary conditions and module boundary guard.
- Updated `tests/test_story_1_2.py::TestLargeDataStubs::test_detect_large_data_returns_false_stub` — the existing stub test was explicitly testing `detect_large_data(1_000_000, 100.0) is False` (stub always False). Since Story 4.1 replaces the stub with real logic, this test was updated to reflect correct implemented behaviour (returns `True` for values exceeding thresholds). The test class name and location were preserved; only the assertion and docstring were updated.
- **Final test count: 304 tests, 0 failures** (287 prior + 17 new). Zero regressions.

### File List

- `utils/large_data.py` — replaced `detect_large_data()` stub with real threshold logic
- `utils/session.py` — added `large_data_detected` and `large_data_message` defaults to `init_session_state()`
- `streamlit_app.py` — updated `_on_csv_upload()` to use detection return value and store in session state; added `st.warning()` inline block to `_execution_panel()`
- `tests/test_large_data.py` — filled empty stub file with 17 unit tests
- `tests/test_story_1_2.py` — updated stub test to reflect implemented behaviour (was testing `return False` stub, now tests real threshold logic)

### Change Log

- Implemented Story 4.1: Large Dataset Detection & Inline Warning (Date: 2026-03-12)
- Code Review (2026-03-12): 6 findings (0 HIGH, 2 MEDIUM, 4 LOW). Fixed: #1 (warning persists after file removal — added else branch to clear flags), #3 (unused import pytest), #4 (duplicate test differentiated), #5 (stale module docstring), #6 (misleading test class name). Deferred: #2 (no integration test for session state wiring — requires Streamlit test harness).

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Date:** 2026-03-12 | **Outcome:** Approved

**Findings:** 0 HIGH, 2 MEDIUM, 4 LOW

**Fixes Applied:**
- [x] [AI-Review][MEDIUM] #1: Added `else` branch at file uploader guard to clear `large_data_detected` and `large_data_message` when user removes files — prevents stale warning persisting with no dataset
- [x] [AI-Review][LOW] #3: Removed unused `import pytest` from `tests/test_large_data.py`
- [x] [AI-Review][LOW] #4: Differentiated duplicate test `test_only_row_threshold_exceeded_returns_true` to use `150_000` instead of `100_001`
- [x] [AI-Review][LOW] #5: Updated stale module docstring in `utils/large_data.py` to reflect Story 4.1 implementation complete
- [x] [AI-Review][LOW] #6: Renamed `TestLargeDataStubs` → `TestLargeDataUtils` in `tests/test_story_1_2.py`

**Deferred Items:**
- [ ] [AI-Review][MEDIUM] #2: No integration test for session state wiring in `_on_csv_upload()` and `_execution_panel()` — requires Streamlit test harness (out of scope)
