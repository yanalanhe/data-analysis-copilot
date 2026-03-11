# Story 3.1: Error Translation Layer & No Silent Failures

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want all pipeline failures to surface a plain-English message in the UI rather than a raw traceback,
so that I always know what happened and what to do next.

## Acceptance Criteria

1. **Given** `utils/error_translation.py` is implemented, **When** an `openai.APIError` is passed to `translate_error()`, **Then** it returns: `"Unable to reach the AI service. Check your API key and connection."`

2. **Given** an `openai.RateLimitError`, **When** passed to `translate_error()`, **Then** it returns: `"AI service rate limit reached. Please wait a moment and try again."`

3. **Given** a `subprocess.TimeoutExpired`, **When** passed to `translate_error()`, **Then** it returns: `"Analysis took too long and was stopped. Try a simpler request or subset your data."`

4. **Given** a `SyntaxError` from AST validation, **When** passed to `translate_error()`, **Then** it returns: `"Generated code had a syntax error — retrying with a corrected approach."`

5. **Given** an `AllowlistViolationError`, **When** passed to `translate_error()`, **Then** it returns: `"Generated code used a restricted operation — retrying with safer code."`

6. **Given** any other `Exception`, **When** passed to `translate_error()`, **Then** it returns: `"An unexpected error occurred. Check the developer console for details."` — never a raw `repr(exception)`

7. **Given** any error surfaced to the user in the UI, **When** I inspect the entire production codebase, **Then** no `st.error(str(e))` or `st.error(repr(e))` calls exist — all errors route through `utils/error_translation.py`

## Tasks / Subtasks

- [x] Task 1: Implement full error taxonomy in `utils/error_translation.py` (AC: #1–6)
  - [x] 1.1: Define `AllowlistViolationError` as a custom exception class in `utils/error_translation.py` (Story 3.3 will import and raise it)
  - [x] 1.2: Replace the stub `translate_error()` body with full `isinstance` dispatch — check `openai.RateLimitError` BEFORE `openai.APIError` (RateLimitError is a subclass; order matters)
  - [x] 1.3: Guard the `import openai` inside translate_error with `try/except ImportError` so unit tests can run without a live openai install (use a try/except block at the top of the function)
  - [x] 1.4: Handle `subprocess.TimeoutExpired`, `SyntaxError`, `AllowlistViolationError`, and fallback `Exception` — all in order, no overlap

- [x] Task 2: Fix the one raw exception display in `streamlit_app.py` (AC: #7)
  - [x] 2.1: In `streamlit_app.py` at line 121, replace `st.error(f"Failed to read **{f.name}**: {e}")` with a call that routes through `translate_error()` — keep the file name context, replace `{e}` with `translate_error(e)`: `st.error(f"Failed to read **{f.name}**: {translate_error(e)}")`
  - [x] 2.2: Add `from utils.error_translation import translate_error` to the imports in `streamlit_app.py` (if not already present)

- [x] Task 3: Write unit tests in `tests/test_error_translation.py` (AC: #1–6)
  - [x] 3.1: Test `openai.APIError` → expected message (mock `openai.APIError` via `unittest.mock.MagicMock` spec if openai is unavailable)
  - [x] 3.2: Test `openai.RateLimitError` → expected message (confirm different from APIError message — this catches the subclass ordering bug)
  - [x] 3.3: Test `subprocess.TimeoutExpired` → expected message (stdlib, no mock needed)
  - [x] 3.4: Test `SyntaxError` → expected message
  - [x] 3.5: Test `AllowlistViolationError` → expected message (import from utils.error_translation)
  - [x] 3.6: Test generic `ValueError` (and `RuntimeError`) → fallback message — confirm no raw exception repr leaked
  - [x] 3.7: Test that the fallback message does NOT contain `repr(exception)` or `str(exception)` content (regression guard)

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing the full error taxonomy in `utils/error_translation.py` — replacing the existing stub
- Defining `AllowlistViolationError` custom exception class in that module (Story 3.3 will `from utils.error_translation import AllowlistViolationError` and raise it)
- Fixing the single raw `st.error(f"... {e}")` call in `streamlit_app.py:121`
- Writing comprehensive unit tests for all 6 taxonomy cases

**IS NOT:**
- Wiring `translate_error()` into pipeline nodes (`pipeline/nodes/codegen.py`, `validator.py`, `executor.py`) — those are Stories 3.2–3.5
- Implementing `validate_code()` or AST checks (Story 3.3)
- Implementing the subprocess sandbox (Story 3.4)
- Implementing `route_after_execution` retry/replan loop (Story 3.5)
- Any changes to the LangGraph graph or pipeline nodes
- Touching `streamlit_app.py:350` — the `return {"passed": False, "errors": [str(e)]}` there is inside the OLD brownfield `execute_plan()` function body. It is NOT a `st.error()` call and is explicitly kept unchanged (backward compat per Story 2-3 notes). Story 3.5 supersedes it.

### Current State (After Story 2-3)

**`utils/error_translation.py` — existing stub (full path: `utils/error_translation.py`):**
```python
# utils/error_translation.py
def translate_error(exception: Exception) -> str:
    """..."""
    # TODO: implement full taxonomy in Story 3.1
    return "An unexpected error occurred. Check the developer console for details."
```

**`tests/test_error_translation.py` — existing stub:**
```python
# tests/test_error_translation.py
# TODO: implement tests in Story 3.1
```

**`streamlit_app.py:121` — the one raw error call to fix:**
```python
        except Exception as e:
            st.error(f"Failed to read **{f.name}**: {e}")  # ← MUST route through translate_error
            continue
```

**Test suite:** 105 tests, 0 failures (from Story 2-3 completion notes). This story must preserve that.

### Required Implementation

**`utils/error_translation.py` — target after Story 3.1:**
```python
# utils/error_translation.py
"""Error translation layer — all pipeline exceptions become plain-English messages here.

All modules must import translate_error from here and call it before displaying any
exception to the user. Never call st.error(str(e)) or st.error(repr(e)) directly.

NOTE: Never import streamlit in this file.
"""
import subprocess


class AllowlistViolationError(Exception):
    """Raised by validate_code() in pipeline/nodes/validator.py when generated code
    contains an import or operation outside the permitted allowlist.
    Story 3.3 imports and raises this; Story 3.1 defines it here as the authoritative location.
    """
    pass


def translate_error(exception: Exception) -> str:
    """Translate an exception to a user-friendly plain-English message.

    Check order matters: openai.RateLimitError MUST be checked before openai.APIError
    because RateLimitError is a subclass of APIError.
    """
    # Guard: openai may not be installed in test environments
    try:
        import openai
        if isinstance(exception, openai.RateLimitError):
            return "AI service rate limit reached. Please wait a moment and try again."
        if isinstance(exception, openai.APIError):
            return "Unable to reach the AI service. Check your API key and connection."
    except ImportError:
        pass

    if isinstance(exception, subprocess.TimeoutExpired):
        return "Analysis took too long and was stopped. Try a simpler request or subset your data."
    if isinstance(exception, SyntaxError):
        return "Generated code had a syntax error — retrying with a corrected approach."
    if isinstance(exception, AllowlistViolationError):
        return "Generated code used a restricted operation — retrying with safer code."
    return "An unexpected error occurred. Check the developer console for details."
```

**`streamlit_app.py:121` — target after Story 3.1:**
```python
        except Exception as e:
            st.error(f"Failed to read **{f.name}**: {translate_error(e)}")
            continue
```

**`tests/test_error_translation.py` — test approach:**
```python
import subprocess
import pytest
from utils.error_translation import translate_error, AllowlistViolationError

def test_translate_syntax_error():
    assert translate_error(SyntaxError("bad syntax")) == \
        "Generated code had a syntax error — retrying with a corrected approach."

def test_translate_allowlist_violation():
    assert translate_error(AllowlistViolationError("import os")) == \
        "Generated code used a restricted operation — retrying with safer code."

def test_translate_subprocess_timeout():
    err = subprocess.TimeoutExpired(cmd="python", timeout=60)
    assert translate_error(err) == \
        "Analysis took too long and was stopped. Try a simpler request or subset your data."

def test_translate_generic_exception():
    result = translate_error(ValueError("something internal"))
    assert result == "An unexpected error occurred. Check the developer console for details."

def test_translate_fallback_does_not_leak_exception_repr():
    """Regression: fallback must never contain raw exception text."""
    exc = RuntimeError("secret internal detail xyz")
    result = translate_error(exc)
    assert "secret internal detail xyz" not in result
    assert "RuntimeError" not in result

# For openai errors — use try/except import guard same as translate_error itself
def test_translate_openai_api_error():
    try:
        import openai
        err = openai.APIError(message="test", request=None, body=None)
        result = translate_error(err)
        assert result == "Unable to reach the AI service. Check your API key and connection."
    except ImportError:
        pytest.skip("openai not installed")

def test_translate_openai_rate_limit_error():
    try:
        import openai
        # RateLimitError must NOT match APIError branch — check subclass ordering
        err = openai.RateLimitError(message="test", response=None, body=None)
        result = translate_error(err)
        assert result == "AI service rate limit reached. Please wait a moment and try again."
        assert result != "Unable to reach the AI service. Check your API key and connection."
    except ImportError:
        pytest.skip("openai not installed")
```

### Architecture Compliance Requirements

- **Module boundary:** `utils/error_translation.py` MUST NOT import `streamlit` — it is a pure utility
- **No inline exception handling:** After this story, no production code may call `st.error(str(e))`, `st.error(repr(e))`, or `st.error(f"...{e}...")` — all must use `translate_error(e)`
- **AllowlistViolationError location:** Defined in `utils/error_translation.py` (authoritative). Story 3.3 does `from utils.error_translation import AllowlistViolationError` when it raises it.
- **Import guard:** The `import openai` inside `translate_error()` must be guarded with `try/except ImportError` — the openai package IS in requirements.txt but test environments may not have it installed
- **Subclass ordering:** `openai.RateLimitError` is a subclass of `openai.APIError`; `isinstance(err, openai.APIError)` would match a RateLimitError. Check `RateLimitError` first.
- **Session state:** No changes to `st.session_state` in this story
- **Pipeline modules:** No changes to any `pipeline/` file in this story

### Testing Strategy

Follow the same mock-light test patterns used in `tests/test_intent.py` and `tests/test_planner.py` — test behaviour directly without heavy mocking.

For `openai` errors: guard with `try/except ImportError` + `pytest.skip` so the test suite can run in environments without openai installed. The `openai` constructor signatures for `APIError` and `RateLimitError` differ between versions — check the installed version's constructor before writing the instantiation.

Alternatively, use `unittest.mock.MagicMock(spec=openai.APIError)` to create mock instances that pass `isinstance` checks without invoking real constructors.

### Previous Story Intelligence (from Story 2-3)

Key patterns and learnings:
- Test file naming convention: `tests/test_story_X_Y.py` for story-level integration tests; `tests/test_<module>.py` for unit tests on a specific module — this story adds to `tests/test_error_translation.py` (module test, not story test)
- `st.rerun()` pattern after state changes — not applicable here (no state changes in this story)
- Code review from Story 2-3 caught: tests must verify behaviour directly, not rely on dict-merge tautologies — apply same rigour here (test that the return value matches the exact expected string)
- The dev model for story 2-3 was `claude-sonnet-4-6` (same model)
- Current working directory for `streamlit run`: project root (`data-analysis-copilot/`)
- All 105 existing tests must continue to pass — `python -m pytest tests/` before and after changes

### Git Intelligence

Recent commits:
- `00618e91` — "Implemented epic-2 defined in sprint-status.yaml" (Epic 2 complete — Stories 2-1, 2-2, 2-3)
- `2540be1d` — "Implemented epic-2-2-1" (Story 2-1 intent classification)
- `d1209faf` — "Implemented epic-1" (Epic 1 foundation)

**Files modified in Epic 2 (regression awareness):**
- `streamlit_app.py` — chat input, plan tab, Execute button wiring
- `pipeline/nodes/intent.py` — `classify_intent()` node
- `pipeline/nodes/planner.py` — `generate_plan()` node
- `utils/session.py` — session defaults including `pipeline_running`, `plan_approved`
- `tests/test_intent.py`, `tests/test_planner.py`, `tests/test_story_2_2.py`, `tests/test_story_2_3.py`

**Do NOT regress:** `st.text()` in Plan tab (not `st.markdown()` — regression from Story 2-2 code review), `plan_approved`/`pipeline_running` reset in `_handle_chat_input()`.

### Project Structure Notes

**Files to modify in Story 3.1:**
- `utils/error_translation.py` — replace stub with full implementation + `AllowlistViolationError` class
- `streamlit_app.py` — fix line 121 raw `st.error` call; add `translate_error` import
- `tests/test_error_translation.py` — replace stub with full unit tests

**No changes to:**
- `pipeline/` — any file (no pipeline changes in this story)
- `utils/session.py` — no changes
- `utils/large_data.py`, `utils/templates.py` — out of scope
- Any existing test files — do not modify, only add

**Alignment with architecture:**
- `utils/error_translation.py` remains importable from `pipeline/` nodes (Stories 3.2–3.5 will import it) ✅
- No `streamlit` import in `utils/error_translation.py` ✅
- `AllowlistViolationError` defined in `utils/` not `pipeline/` — keeps it importable from both layers ✅
- One scoped change to `streamlit_app.py` — minimal footprint ✅

### References

- Epic 3, Story 3.1 definition: [Source: _bmad-output/planning-artifacts/epics.md#story-31-error-translation-layer--no-silent-failures]
- Architecture — error taxonomy table: [Source: _bmad-output/planning-artifacts/architecture.md#error-taxonomy]
- Architecture — communication patterns: [Source: _bmad-output/planning-artifacts/architecture.md#communication-patterns]
- Architecture — enforcement guidelines: [Source: _bmad-output/planning-artifacts/architecture.md#enforcement-guidelines]
- Existing stub to replace: [utils/error_translation.py](utils/error_translation.py)
- Existing test stub to replace: [tests/test_error_translation.py](tests/test_error_translation.py)
- Raw error call to fix: [streamlit_app.py:121](streamlit_app.py#L121)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Replaced stub `utils/error_translation.py` with full 6-case error taxonomy. Defined `AllowlistViolationError` custom exception class as the authoritative location for Story 3.3 to import and raise.
- `translate_error()` checks `openai.RateLimitError` before `openai.APIError` (subclass ordering) inside a `try/except ImportError` guard for test-environment safety.
- Fixed `streamlit_app.py` CSV upload handler (line 122): replaced `st.error(f"... {e}")` with `st.error(f"... {translate_error(e)}")`. Added `from utils.error_translation import translate_error` import.
- Replaced stub `tests/test_error_translation.py` with 10 unit tests covering all 6 AC taxonomy cases plus subclass ordering regression guard and two leak-prevention guards.
- Full regression suite: **115 tests, 0 failures** (105 pre-existing + 10 new).
- Code review fixes (2026-03-11): Added logging for unhandled fallback exceptions, self-protection wrapper, UnicodeDecodeError and pd.errors.ParserError cases to preserve CSV diagnostic context. 2 new tests added. **117 tests, 0 failures**.

### File List

- `utils/error_translation.py` — replaced stub with full taxonomy + `AllowlistViolationError` class; added logging, self-protection, file I/O error cases
- `streamlit_app.py` — added `translate_error` import; fixed CSV upload error display (line 122)
- `tests/test_error_translation.py` — replaced stub with 12 unit tests

### Change Log

- Implemented Story 3.1: Error Translation Layer & No Silent Failures (Date: 2026-03-11)
- Code review fixes: Added fallback logging, self-protection, UnicodeDecodeError + ParserError taxonomy (Date: 2026-03-11)
