# Story 4.2: Auto-Downsampling Recovery Path

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want the system to automatically downsample my large dataset to a manageable size and offer a manual subset alternative,
so that I can still get a useful visualization and analysis even with very large CSV files.

## Acceptance Criteria

1. **Given** large data is detected and the inline warning is shown, **When** I view the warning message, **Then** at least one recovery action is offered: an "Auto-downsample to 10,000 points" button is clearly visible (FR28)

2. **Given** I click the auto-downsample button, **When** `apply_uniform_stride()` from `utils/large_data.py` runs, **Then** uniform stride sampling reduces the combined dataset to 10,000 rows before writing the session temp CSV file

3. **Given** auto-downsampling has been applied, **When** I run analysis, **Then** the pipeline runs on the downsampled data and produces charts and trend analysis successfully

4. **Given** downsampling has been applied and the report panel shows results, **When** I view the report, **Then** a note is visible alongside the charts: "Downsampled to 10,000 points using uniform stride" — so I understand the tradeoff

5. **Given** the inline large data warning, **When** I read it, **Then** it also suggests filtering the data in the editable data table as an alternative recovery path (FR28)

6. **Given** no recovery action is taken and I attempt to run the pipeline with large data, **When** the pipeline processes the request, **Then** a clear user-readable message is surfaced — no silent failure, no raw traceback (NFR8, FR29)

## Tasks / Subtasks

- [x] Task 1: Implement `apply_uniform_stride()` in `utils/large_data.py` (AC: #2)
  - [x] 1.1: Replace the `# TODO: implement in Story 4.2` stub with real uniform stride logic
  - [x] 1.2: Calculate stride as `max(1, len(df) // target_rows)` — prevents zero-division for small datasets
  - [x] 1.3: Select rows using `df.iloc[::stride].head(target_rows).reset_index(drop=True)` — uniform coverage, capped to target
  - [x] 1.4: If `len(df) <= target_rows`: return `df` unchanged — no downsampling needed for already-small datasets
  - [x] 1.5: Do NOT import streamlit — pure utility function (module boundary rule)
  - [x] 1.6: `target_rows` parameter defaults to `DOWNSAMPLE_TARGET_ROWS` (10_000) — use the existing constant

- [x] Task 2: Add `recovery_applied` to `init_session_state()` in `utils/session.py` (AC: #3, #4)
  - [x] 2.1: Add `"recovery_applied": ""` to the `defaults` dict in `init_session_state()` — empty string means no recovery taken
  - [x] 2.2: Valid values: `""` (none), `"downsampled"` (auto-downsampled applied) — consistent with `PipelineState.recovery_applied` field
  - [x] 2.3: Idempotent — only sets key if not already present (consistent with existing pattern)

- [x] Task 3: Update `_on_csv_upload()` in `streamlit_app.py` to reset recovery state on new upload (AC: #2, #3)
  - [x] 3.1: When a new upload is processed (after the signature guard passes), reset `st.session_state["recovery_applied"] = ""`
  - [x] 3.2: This ensures that uploading a new file clears any previously applied downsampling state — prevents stale recovery state from a prior session

- [x] Task 4: Add "Auto-downsample" button and recovery note to `_execution_panel()` in `streamlit_app.py` (AC: #1, #4, #5, #6)
  - [x] 4.1: In `_execution_panel()`, after the existing `st.warning(large_data_message)` call (Story 4.1), add the downsample button block
  - [x] 4.2: Only show the button when `large_data_detected` is `True` AND `recovery_applied` is NOT `"downsampled"` (no double-downsampling)
  - [x] 4.3: Button label: `"Auto-downsample to 10,000 points"` — matches exact wording in the epics AC
  - [x] 4.4: On button click: call `_apply_downsample()`, set `recovery_applied = "downsampled"`, call `st.rerun()` to refresh the panel
  - [x] 4.5: After button block: when `recovery_applied == "downsampled"`, show `st.success("Downsampled to 10,000 points using uniform stride.")` — this note persists through chart rendering
  - [x] 4.6: Update the warning message text displayed in `_execution_panel()` to also suggest: "You can also filter your data in the editable data table before running analysis." — appended at display time (no change to stored session state message)
  - [x] 4.7: AC #6 — added `st.warning` inline in report panel when `large_data_detected and recovery == "" and ps and ps.get("error_messages")`: "Analysis ran on the full large dataset. Results may be incomplete or unrenderable."

- [x] Task 5: Wire the downsample button's DataFrame access safely (AC: #2, #3)
  - [x] 5.1: `_apply_downsample()` accesses combined DataFrame via single/multi-file logic matching `_on_csv_upload()` — `pd.concat(...)` for multi, `list(...)[0]` for single
  - [x] 5.2: After downsampling, writes to temp file using the SAME path as `st.session_state["csv_temp_path"]` (overwrite) — fallback creates new temp file if path missing
  - [x] 5.3: `apply_uniform_stride` imported inside `_apply_downsample()` (lazy import, consistent with `_on_csv_upload()` pattern)
  - [x] 5.4: Guard against `uploaded_dfs` being empty: shows `st.warning("No uploaded dataset found. Please upload a CSV file first.")` and returns early

- [x] Task 6: Write tests in `tests/test_large_data.py` for `apply_uniform_stride()` (AC: #2)
  - [x] 6.1: `apply_uniform_stride` imported inside each test method (consistent with file's pattern)
  - [x] 6.2: Test: DataFrame with 100,000 rows → result has exactly 10,000 rows (`DOWNSAMPLE_TARGET_ROWS`)
  - [x] 6.3: Test: DataFrame with 50,000 rows → result has exactly 10,000 rows (also above threshold)
  - [x] 6.4: Test: DataFrame with 9,999 rows → result has 9,999 rows unchanged (below target, no downsampling)
  - [x] 6.5: Test: DataFrame with 10,000 rows → result has 10,000 rows unchanged (exactly at target)
  - [x] 6.6: Test: DataFrame with 10,001 rows → result has 10,000 rows (just above target — downsampling kicks in)
  - [x] 6.7: Test: uniform stride preserves column names — input columns == output columns
  - [x] 6.8: Test: result index is reset (`reset_index(drop=True)`) — output index starts at 0 and is contiguous
  - [x] 6.9: Test: stride coverage is uniform — result max value > 40,000 (not just first N rows of a 50k dataset)
  - [x] 6.10: Test: `apply_uniform_stride(df, target_rows=5)` with a 20-row df returns exactly 5 rows
  - [x] 6.11: Test: empty DataFrame returns empty DataFrame without error
  - [x] 6.12: Test: single-row DataFrame returns that row unchanged

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing `apply_uniform_stride()` in `utils/large_data.py` (replacing the `return df` stub)
- Adding "Auto-downsample to 10,000 points" button in `_execution_panel()` in `streamlit_app.py`
- Writing the downsampled data to the existing temp CSV path (overwriting it)
- Showing "Downsampled to 10,000 points using uniform stride" note in the report panel
- Updating the warning text to include filter-in-table suggestion
- Adding `recovery_applied` to `init_session_state()` in `utils/session.py`
- Resetting `recovery_applied` when a new file is uploaded
- Writing tests for `apply_uniform_stride()`

**IS NOT:**
- Modifying `detect_large_data()` — already implemented and tested (Story 4.1)
- Changing the `large_data_detected` / `large_data_message` session state logic — already works from Story 4.1
- Modifying any pipeline node — this is a UI-layer and utils story only
- Modifying `PipelineState` — `recovery_applied` field already exists (`pipeline/state.py`)
- Adding modal dialogs — UX spec explicitly forbids modals (inline only)

---

### References

- Epic 4, Story 4.2 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-42-auto-downsampling-recovery-path]
- Architecture — large data process pattern and uniform stride: [Source: _bmad-output/planning-artifacts/architecture.md#process-patterns]
- Architecture — large data user message pattern (full message including filter hint): [Source: _bmad-output/planning-artifacts/architecture.md#frontend-architecture]
- Architecture — `recovery_applied` in PipelineState: [Source: _bmad-output/planning-artifacts/architecture.md#data-architecture]
- FR28: "at least one recovery path when a dataset is too large — either automatic downsampling or prompt to subset/reduce": [Source: _bmad-output/planning-artifacts/epics.md#requirements-inventory]
- NFR8: "All execution failures surface a user-readable message — no silent failures": [Source: _bmad-output/planning-artifacts/epics.md#nonfunctional-requirements]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `apply_uniform_stride(df, target_rows)` in `utils/large_data.py` — replaced the `return df` stub with: guard for `len(df) <= target_rows` (returns unchanged), stride = `max(1, len(df) // target_rows)`, selection via `df.iloc[::stride].head(target_rows).reset_index(drop=True)`. No streamlit import — pure utility function. Uniform coverage confirmed by test asserting `result.max() > 40_000` on a 50k dataset.
- Added `"recovery_applied": ""` to the `defaults` dict in `init_session_state()` in `utils/session.py`. Idempotent — only sets key if not already present. Mirrors the `recovery_applied: str` field already in `PipelineState`.
- Updated `_on_csv_upload()` in `streamlit_app.py` — after the `_upload_signature` guard (only fires when new files are actually processed), resets `st.session_state["recovery_applied"] = ""`. Prevents stale recovery state when user uploads a new file after previously downsampling.
- Updated the `else` (file removal) branch at the file uploader to also clear `st.session_state["recovery_applied"] = ""` alongside existing `large_data_detected` and `large_data_message` clears.
- Added `_apply_downsample()` private helper function in `streamlit_app.py` — reconstructs combined DataFrame from `uploaded_dfs`, calls `apply_uniform_stride()`, overwrites temp CSV at `csv_temp_path`, updates `st.session_state.df` for backward compat, sets `recovery_applied = "downsampled"`. Guards against empty `uploaded_dfs`.
- Updated `_execution_panel()` in `streamlit_app.py` — replaced the Story 4.1 simple `st.warning` block with expanded 4.2 block: reads `large_data` and `recovery` state variables; appends filter-in-table hint to warning message at display time; shows "Auto-downsample to 10,000 points" button when `large_data=True` and `recovery != "downsampled"`; shows `st.success("Downsampled to 10,000 points using uniform stride.")` when recovery applied; adds AC #6 warning after report render block for unsampled large data runs with errors.
- Added `TestApplyUniformStride` class with 11 tests to `tests/test_large_data.py`. Covers all 12 subtasks (6.1–6.12): 100k→10k, 50k→10k, 9999 unchanged, exactly at target unchanged, 10001→10k, column preservation, index reset, uniform coverage (not just head), custom target_rows, empty DataFrame, single-row DataFrame.
- **Final test count: 315 tests, 0 failures** (304 prior + 11 new). Zero regressions.

### File List

- `utils/large_data.py` — replaced `apply_uniform_stride()` stub with real uniform stride downsampling logic
- `utils/session.py` — added `"recovery_applied": ""` to `init_session_state()` defaults dict
- `streamlit_app.py` — added `_apply_downsample()` helper; updated `_on_csv_upload()` to reset `recovery_applied` on new upload; updated file-removal `else` branch to clear `recovery_applied`; updated `_execution_panel()` with expanded 4.2 large-data block (button, filter hint, recovery note, AC #6 warning)
- `tests/test_large_data.py` — added `TestApplyUniformStride` class with 11 unit tests
- `tests/test_story_1_2.py` — updated `TestLargeDataStubs` → `TestLargeDataUtils`, fixed stale stub assertions to match real implementation

### Change Log

- Implemented Story 4.2: Auto-Downsampling Recovery Path (Date: 2026-03-12)
- Code review completed (Date: 2026-03-12): Fixed 5 issues — H1: updated stale stub test in test_story_1_2.py; M1: added test_story_1_2.py to File List; M2: broadened AC #6 warning condition to cover execution_success=False; M3: extracted _combine_uploaded_dfs() helper to eliminate duplicated logic; M4: updated stale module docstring in large_data.py
