# Story 6.2: LLM API Resilience & Developer Error Reporting

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the app to surface clear errors when the LLM API is unavailable and provide human-readable error output for debugging,
so that I can quickly diagnose and resolve issues without reading raw stack traces.

## Acceptance Criteria

1. **Given** the OpenAI API is unreachable or returns an `openai.APIError`, **When** the pipeline runs, **Then** the user sees: "Unable to reach the AI service. Check your API key and connection." — not a raw exception (NFR14)

2. **Given** a pipeline failure at any node, **When** the error is caught and translated, **Then** `pipeline_state["error_messages"]` contains a human-readable description of what failed — visible to developers via the LangSmith trace (FR32)

3. **Given** `OPENAI_API_KEY` is missing from `.env`, **When** I submit a query, **Then** the error message identifies the missing key and provides an actionable next step ("Add OPENAI_API_KEY to your .env file")

4. **Given** the app is run without any LangSmith configuration, **When** it starts and I run the standard workflow (upload → query → execute → report), **Then** startup is clean, the workflow completes successfully, and no warnings about missing optional configuration appear (NFR15, NFR16)

5. **Given** `requirements.txt`, **When** I inspect it, **Then** all Python library dependencies are explicitly pinned to exact versions — ensuring consistent behavior across local installations (NFR16)

## Tasks / Subtasks

- [x] Task 1: Add `openai.AuthenticationError` handling to `utils/error_translation.py` for missing API key detection (AC: #1, #3)
  - [x] 1.1: In `_translate_error_inner()` in `utils/error_translation.py`, add `openai.AuthenticationError` check **before** the existing `openai.APIError` check (AuthenticationError is a subclass of APIError — order matters). Return the actionable message: `"Add OPENAI_API_KEY to your .env file"`
    ```python
    if isinstance(exception, openai.AuthenticationError):
        return "Add OPENAI_API_KEY to your .env file"
    if isinstance(exception, openai.RateLimitError):
        return "AI service rate limit reached. Please wait a moment and try again."
    if isinstance(exception, openai.APIError):
        return "Unable to reach the AI service. Check your API key and connection."
    ```
  - [x] 1.2: Verify the check order is `AuthenticationError` → `RateLimitError` → `APIError` (all three are subclasses of `APIError`; the most specific must be checked first)
  - [x] 1.3: Confirm the existing `try/except ImportError` guard around the openai block still wraps all three checks — the guard prevents crashes in environments without the `openai` package

- [x] Task 2: Verify end-to-end error propagation: APIError → `pipeline_state["error_messages"]` (AC: #1, #2)
  - [x] 2.1: Trace the path from `openai.APIError` → `translate_error()` → `error_messages`. Check `pipeline/nodes/codegen.py` (~line 86): confirm `except Exception as e: error_msg = translate_error(e)` and then `"error_messages": existing_errors + [error_msg]` is returned. This already exists — verify, do not modify.
  - [x] 2.2: Check `pipeline/nodes/intent.py` and `pipeline/nodes/planner.py` — both use `ChatOpenAI(model="gpt-4o", temperature=0)`. Verify each node has an `except Exception as e` block that calls `translate_error(e)` and returns `{"error_messages": ..., "execution_success": False}` (or equivalent). If any node catches exceptions without going through `translate_error()`, fix it.
  - [x] 2.3: Verify `run_pipeline()` in `pipeline/graph.py` (~line 108) also has `except Exception as e: translate_error(e)` as the outer safety net. This was confirmed working in Story 6.1 — verify it's still intact.
  - [x] 2.4: Confirm `error_messages` values appear in LangSmith traces automatically: since `run_pipeline()` is decorated with `@_traceable(name="analysis_pipeline")`, any returned `PipelineState` (including `error_messages`) is captured by LangGraph's tracing. No additional instrumentation is needed.

- [x] Task 3: Verify app starts cleanly without LangSmith configuration (AC: #4)
  - [x] 3.1: Verify `initialize_environment()` in `streamlit_app.py` (after Story 6.1 fix) does NOT force-set any LangSmith env vars. It should only call `load_dotenv()`, then instantiate `LangSmithClient()` inside `try/except`, then create `OpenAI()` client. Confirm the fix from Story 6.1 is intact.
  - [x] 3.2: Confirm the `_traceable` import fallback in `pipeline/graph.py` is present:
    ```python
    try:
        from langsmith import traceable as _traceable
    except ImportError:  # pragma: no cover
        def _traceable(name=None, **kwargs):
            def decorator(fn):
                return fn
            return decorator
    ```
    This prevents any crash if `langsmith` is uninstalled.
  - [x] 3.3: Confirm no `st.warning()`, `st.info()`, or `print()` calls exist anywhere that would fire when `LANGSMITH_API_KEY` is absent. Search: `grep -rn "LANGSMITH" streamlit_app.py pipeline/ utils/` — should only appear in `utils/session.py` (if used there) or `streamlit_app.py`'s `initialize_environment()`, not in any display or warning call.

- [x] Task 4: Verify `requirements.txt` is fully pinned (AC: #5)
  - [x] 4.1: Inspect `requirements.txt`. Every line must match the pattern `package==x.y.z` (exact version pin). Lines with `>=`, `~=`, `^`, or no version specifier are violations.
  - [x] 4.2: If any un-pinned entries exist, pin them to the currently installed version: `pip freeze | grep <package_name>` to find the exact version, then update `requirements.txt`.
  - [x] 4.3: Confirm these key packages are present and pinned (from architecture doc and prior stories):
    - `openai==1.109.1`
    - `langsmith==0.7.0`
    - `langchain==0.3.27`
    - `langchain-openai==0.3.35`
    - `python-dotenv==1.0.1`
    - `streamlit==1.40.2` (or whatever version was installed in Story 1.1)

- [x] Task 5: Write tests in `tests/test_api_resilience.py` (AC: #1–#5)
  - [x] 5.1: Test `openai.AuthenticationError` → "Add OPENAI_API_KEY..." message (AC #3):
    ```python
    def test_translate_authentication_error():
        import openai
        err = openai.AuthenticationError(
            message="No API key provided",
            response=unittest.mock.MagicMock(status_code=401, headers={}),
            body={"error": {"message": "No API key provided"}},
        )
        result = translate_error(err)
        assert result == "Add OPENAI_API_KEY to your .env file"
    ```
  - [x] 5.2: Test `openai.APIError` → "Unable to reach the AI service..." message (AC #1):
    ```python
    def test_translate_api_error():
        import openai
        err = openai.APIConnectionError(request=unittest.mock.MagicMock())
        result = translate_error(err)
        assert result == "Unable to reach the AI service. Check your API key and connection."
    ```
  - [x] 5.3: Test `openai.RateLimitError` → rate limit message (existing taxonomy, but confirm still works):
    ```python
    def test_translate_rate_limit_error():
        import openai
        err = openai.RateLimitError(
            message="Rate limit exceeded",
            response=unittest.mock.MagicMock(status_code=429, headers={}),
            body={"error": {"message": "Rate limit"}},
        )
        result = translate_error(err)
        assert result == "AI service rate limit reached. Please wait a moment and try again."
    ```
  - [x] 5.4: Test `AuthenticationError` returns different message than generic `APIError` (ensures subclass ordering is correct) (AC #3):
    ```python
    def test_authentication_error_is_more_specific_than_api_error():
        import openai
        auth_err = openai.AuthenticationError(
            message="Invalid API key",
            response=unittest.mock.MagicMock(status_code=401, headers={}),
            body={"error": {"message": "Invalid API key"}},
        )
        api_err = openai.APIConnectionError(request=unittest.mock.MagicMock())
        auth_msg = translate_error(auth_err)
        api_msg = translate_error(api_err)
        assert auth_msg != api_msg
        assert "OPENAI_API_KEY" in auth_msg  # actionable
        assert ".env" in auth_msg            # tells them where to fix it
    ```
  - [x] 5.5: Test `run_pipeline()` propagates APIError into `error_messages` as human-readable (AC #2):
    ```python
    def test_api_error_propagates_as_human_readable(monkeypatch):
        import openai
        from pipeline.graph import run_pipeline
        minimal_state = {
            "user_query": "test", "csv_temp_path": None, "data_row_count": 0,
            "intent": "report", "plan": [], "generated_code": "",
            "validation_errors": [], "execution_output": "", "execution_success": False,
            "retry_count": 0, "replan_triggered": False, "error_messages": [],
            "report_charts": [], "report_text": "", "large_data_detected": False,
            "large_data_message": "", "recovery_applied": "",
        }
        api_error = openai.APIConnectionError(request=unittest.mock.MagicMock())
        with unittest.mock.patch("pipeline.graph.compiled_graph") as mock_graph:
            mock_graph.invoke.side_effect = api_error
            result = run_pipeline(minimal_state)
        assert result["execution_success"] is False
        msgs = result.get("error_messages", [])
        assert len(msgs) > 0
        # Must be translated — not raw repr
        assert "APIConnectionError" not in msgs[0]
        assert "Unable to reach" in msgs[0]  # the taxonomy message
    ```
  - [x] 5.6: Test `requirements.txt` has no un-pinned entries (AC #5):
    ```python
    def test_requirements_all_pinned():
        content = pathlib.Path("requirements.txt").read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Must have == (exact pin), not >=, ~=, etc.
            assert "==" in line, f"Unpinned dependency in requirements.txt: {line!r}"
            assert ">=" not in line, f"Unpinned dependency (>=): {line!r}"
            assert "~=" not in line, f"Unpinned dependency (~=): {line!r}"
    ```
  - [x] 5.7: Test no `st.error(str(e))` or `st.error(repr(e))` patterns exist (confirms FR32 — all errors go through translate_error) (AC #2):
    ```python
    def test_no_raw_exception_to_ui():
        import re
        raw_pattern = re.compile(r'st\.error\(\s*(str|repr)\s*\(')
        for path in [
            pathlib.Path("streamlit_app.py"),
            *pathlib.Path("pipeline").rglob("*.py"),
            *pathlib.Path("utils").rglob("*.py"),
        ]:
            content = path.read_text(encoding="utf-8", errors="replace")
            matches = raw_pattern.findall(content)
            assert not matches, f"Raw exception to UI in {path}: {matches}"
    ```

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Adding `openai.AuthenticationError` handling in `utils/error_translation.py` with the specific actionable message "Add OPENAI_API_KEY to your .env file"
- Verifying (not modifying) the end-to-end APIError → `error_messages` propagation path through all nodes and `run_pipeline()`
- Verifying (not modifying) the app starts cleanly without LangSmith config (this was fixed in Story 6.1)
- Verifying (not modifying) `requirements.txt` is fully pinned — fix if violations found
- Writing tests for all 5 ACs in `tests/test_api_resilience.py`

**IS NOT:**
- Adding any new LangSmith tracing (Story 6.1 already did this)
- Modifying `pipeline/graph.py` or any node beyond error handling fixes
- Adding any UI-level error display changes — errors are already surfaced via the existing `st.status` + `error_messages` path
- Changing the `@_traceable` scope or pattern (Story 6.1 already verified this)
- Adding retry logic for API failures — retries are already handled by the LangGraph loop

---

### Critical New Code: `utils/error_translation.py` Change

The ONLY mandatory code change is in `_translate_error_inner()`. Add the `AuthenticationError` branch before the `APIError` branch:

**Current state (after Story 3.1 / 6.1):**
```python
try:
    import openai
    if isinstance(exception, openai.RateLimitError):
        return "AI service rate limit reached. Please wait a moment and try again."
    if isinstance(exception, openai.APIError):
        return "Unable to reach the AI service. Check your API key and connection."
except ImportError:
    pass
```

**Required state after Story 6.2:**
```python
try:
    import openai
    if isinstance(exception, openai.AuthenticationError):
        return "Add OPENAI_API_KEY to your .env file"
    if isinstance(exception, openai.RateLimitError):
        return "AI service rate limit reached. Please wait a moment and try again."
    if isinstance(exception, openai.APIError):
        return "Unable to reach the AI service. Check your API key and connection."
except ImportError:
    pass
```

**Why `AuthenticationError` before `APIError`:**
In the OpenAI SDK v1.x hierarchy:
- `openai.APIError` (base)
  - `openai.APIStatusError` (has HTTP status code)
    - `openai.AuthenticationError` (HTTP 401 — invalid/missing API key)
    - `openai.RateLimitError` (HTTP 429)
    - `openai.NotFoundError` (HTTP 404)
  - `openai.APIConnectionError` (no HTTP response — network unreachable)

Both `AuthenticationError` and `RateLimitError` are subclasses of `APIError`. The check order must go most-specific → least-specific. If `APIError` is checked first, it matches `AuthenticationError` too and the specific message is never reached.

**When `AuthenticationError` is raised:**
- `OPENAI_API_KEY` is absent from `.env` (key is `None`) → `ChatOpenAI` raises on first LLM call
- `OPENAI_API_KEY` is present but invalid → OpenAI API returns HTTP 401

---

### Current Error Path (Already Working — Verify Only)

Every pipeline node already has this pattern (confirm in `intent.py`, `planner.py`, `codegen.py`):

```python
try:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # ... invoke llm ...
    return {"intent": result}  # changed keys only
except Exception as e:
    from utils.error_translation import translate_error
    error_msg = translate_error(e)
    return {
        "error_messages": list(state.get("error_messages", [])) + [error_msg],
        "execution_success": False,
    }
```

And `run_pipeline()` in `pipeline/graph.py` has the outer safety net:
```python
@_traceable(name="analysis_pipeline")
def run_pipeline(state: PipelineState) -> PipelineState:
    try:
        result = compiled_graph.invoke(state)
        return result
    except Exception as e:
        from utils.error_translation import translate_error
        error_msg = translate_error(e)
        return {
            **state,
            "execution_success": False,
            "error_messages": list(state.get("error_messages", [])) + [error_msg],
        }
```

The `error_messages` list is visible in the LangSmith trace because `run_pipeline()` is decorated with `@_traceable`. LangSmith captures the full `PipelineState` returned by the function.

---

### How `error_messages` Surface to the User (Existing Pattern)

In `streamlit_app.py`, after `run_pipeline()` returns, the execution fragment reads `error_messages` and displays them via the `st.status` context or inline in the report panel. This path was implemented in Story 3.1 (error translation layer) and Story 3.6 (non-blocking execution panel). No changes to this display logic are needed for Story 6.2.

---

### How `ChatOpenAI` Gets the API Key (Important for AC3)

`ChatOpenAI(model="gpt-4o", temperature=0)` is initialized inside each node function call (not at module load time). It reads `OPENAI_API_KEY` from the environment automatically via the `openai` SDK. If the key is absent:
- The `ChatOpenAI` constructor may succeed (it doesn't validate on init)
- The API call fails on the first `.invoke()` with `openai.AuthenticationError`

This means the error is caught by the node's `except Exception as e` block → `translate_error(e)` → the new `AuthenticationError` branch → "Add OPENAI_API_KEY to your .env file" → stored in `error_messages` → returned to UI layer.

---

### Session State Schema Reference

No new `st.session_state` keys are added in this story. The `error_messages` field is already part of `PipelineState` (not session state). Session state schema remains:
```python
{
    "uploaded_dfs": dict,
    "csv_temp_path": str | None,
    "chat_history": list[dict],
    "pipeline_state": PipelineState | None,
    "pipeline_running": bool,
    "plan_approved": bool,
    "active_tab": Literal["plan", "code", "template"],
    "saved_templates": list[dict],
    "active_template": dict | None,
}
```

---

### Architecture Compliance

- **Error taxonomy (NFR8, FR29):** All exceptions MUST route through `utils/error_translation.py`. Adding `AuthenticationError` to the taxonomy table is the correct approach — no inline error handling anywhere else. [Source: _bmad-output/planning-artifacts/architecture.md#Communication-Patterns]
- **Module boundary:** The fix is in `utils/error_translation.py` — the designated location for all error translation. No pipeline or UI code changes. [Source: architecture.md#Utils-Boundary]
- **LangSmith non-blocking (NFR15):** Already implemented in Story 6.1. Verified-only in this story. [Source: architecture.md#Communication-Patterns]
- **All deps pinned (NFR16):** `requirements.txt` must use `==` for all entries. [Source: architecture.md#Infrastructure-Deployment]
- **No `streamlit` imports in utils:** `utils/error_translation.py` must never import streamlit — it is a pure Python utility. The docstring already states this. [Source: architecture.md#Enforcement-Guidelines]

---

### Previous Story Intelligence (from Story 6.1)

- **362 tests passing** at end of Story 6.1 — all must remain green after this story
- Story 6.1 established: `initialize_environment()` does NOT force-set `LANGCHAIN_TRACING_V2` — this is already done; verify-only for AC4
- Pattern from Story 6.1 tests: `pathlib.Path("...").read_text(encoding="utf-8", errors="replace")` for Windows compatibility with cp1252 encoding
- `monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)` pattern used to isolate env vars in tests
- `unittest.mock.patch("pipeline.graph.compiled_graph")` pattern used to mock the graph
- AST-based structural tests used to verify decorator patterns — follow same approach for structural checks
- Story 6.1 note: `test_initialize_environment_does_not_force_tracing` initially failed with `UnicodeDecodeError` on Windows — always use `encoding="utf-8", errors="replace"` when reading files in tests

**What Story 6.1 already completed (do NOT redo):**
- Fixed `initialize_environment()` to remove hardcoded `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY` env var force-sets
- Verified `@_traceable` on `run_pipeline()` only
- Verified `.env.example` documents all 4 keys
- Created `tests/test_langsmith_integration.py` with 10 tests

---

### Git Intelligence (Recent Work)

```
4441ccae Implemented story 6-1-langsmith-tracing-integration  ← Story 6.1 done
66e46ae4 Implemented epic-5 template system                   ← Epic 5 complete
e7391475 Implemented epic-5 Code Transparency
8a56ca40 Implemented epic-4 Large Data Resilience
60e038e0 Implemented story 3-6-non-blocking-execution-panel-visual-report-rendering
```

This is the **final story** in the project (all other epics are done). After Story 6.2, all 32 FRs and 16 NFRs are covered. The PR (git diff on the `bmad` branch vs `main`) should be created after code review passes.

---

### openai SDK Error Hierarchy (v1.109.1 — pinned version)

Relevant exception types for implementing and testing AC1, AC3:

```
openai.OpenAIError (base)
└── openai.APIError (base for all API errors)
    ├── openai.APIConnectionError  → network unreachable, DNS failure, timeout
    │   └── openai.APITimeoutError → specifically a timeout
    └── openai.APIStatusError      → HTTP response received (has .status_code)
        ├── openai.AuthenticationError  (HTTP 401) ← ADD THIS to taxonomy
        ├── openai.PermissionDeniedError (HTTP 403)
        ├── openai.NotFoundError        (HTTP 404)
        ├── openai.UnprocessableEntityError (HTTP 422)
        ├── openai.RateLimitError       (HTTP 429) ← ALREADY in taxonomy
        └── openai.InternalServerError  (HTTP 5xx)
```

When creating `openai.AuthenticationError` for tests, it requires `message`, `response`, and `body` parameters (APIStatusError interface). Use `unittest.mock.MagicMock()` for the response object.

---

### Key File Locations

| File | Change | Purpose |
|---|---|---|
| `utils/error_translation.py` | Modify `_translate_error_inner()` | Add `openai.AuthenticationError` before `openai.APIError` check — returns "Add OPENAI_API_KEY to your .env file" |
| `pipeline/nodes/intent.py` | Verify only — no changes expected | Confirm `except Exception as e` → `translate_error(e)` present |
| `pipeline/nodes/planner.py` | Verify only — no changes expected | Confirm `except Exception as e` → `translate_error(e)` present |
| `pipeline/nodes/codegen.py` | Verify only — no changes expected | Already confirmed in Story 6.1 context |
| `pipeline/graph.py` | Verify only — no changes expected | `run_pipeline()` outer safety net confirmed in Story 6.1 |
| `requirements.txt` | Verify + fix if needed | All entries must use `==` pinning |
| `tests/test_api_resilience.py` | New file | 7 tests covering all 5 ACs |

---

### Project Context Reference

- Architecture rule: all exceptions → `utils/error_translation.py` → human-readable string → `error_messages` list. Never `st.error(str(e))` or `repr(e)` directly. [Source: _bmad-output/planning-artifacts/architecture.md#Communication-Patterns]
- Architecture rule: `requirements.txt` fully pinned for reproducibility across local installations (NFR16). [Source: architecture.md#Infrastructure-Deployment]
- Architecture error taxonomy table: [Source: architecture.md#Communication-Patterns]
  - `openai.AuthenticationError` → "Add OPENAI_API_KEY to your .env file" ← NEW
  - `openai.APIError` → "Unable to reach the AI service. Check your API key and connection."
  - `openai.RateLimitError` → "AI service rate limit reached. Please wait a moment and try again."
  - `subprocess.TimeoutExpired` → "Analysis took too long..."
  - `SyntaxError` → "Generated code had a syntax error..."
  - `AllowlistViolationError` → "Generated code used a restricted operation..."
  - All other `Exception` → "An unexpected error occurred..."
- `openai==1.109.1` is the pinned version in `requirements.txt` — this defines the error hierarchy to code against.
- 362 tests currently passing (baseline from Story 6.1) — all must remain green.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Tests `test_exception_returns_only_intent_key` (test_intent.py) and `test_generate_plan_error_handling` (test_planner.py) were checking old incorrect behavior (silent error swallowing). Updated both tests to verify the correct behavior: errors propagated to `error_messages` via `translate_error()`.
- Test `test_no_raw_exception_to_ui` initially matched docstring text in `utils/error_translation.py` (line referencing `st.error(str(e))`). Fixed regex from `r"st\.error\(\s*(str|repr)\s*\("` to line-anchored `r"^\s*st\.error\(\s*(str|repr)\s*\("` with `re.MULTILINE` to skip docstring/comment mentions.

### Completion Notes List

- Added `openai.AuthenticationError` check to `utils/error_translation.py` in `_translate_error_inner()`, positioned before `openai.RateLimitError` and `openai.APIError` (both of which are parent classes). Returns `"Add OPENAI_API_KEY to your .env file"` for HTTP 401 responses (AC3).
- Fixed `pipeline/nodes/intent.py`: replaced silent `except Exception: intent = "chat"` with proper `translate_error(e)` call that returns both `intent: "chat"` fallback AND `error_messages: [translated_msg]` (AC2, FR29).
- Fixed `pipeline/nodes/planner.py`: replaced inline `"Error generating plan. Please try again."` with proper `translate_error(e)` call returning `plan: []` and `error_messages: [translated_msg]` (AC2, FR29).
- Verified `pipeline/graph.py` `run_pipeline()` outer `try/except` with `translate_error()` intact (Story 6.1 verified) (AC2).
- Verified `initialize_environment()` in `streamlit_app.py` does not force-set LangSmith env vars (Story 6.1 fix intact) (AC4).
- Verified `requirements.txt` all pinned with `==` — test passes (AC5).
- Created `tests/test_api_resilience.py` with 7 tests covering all 5 ACs.
- Updated `tests/test_intent.py::test_exception_returns_only_intent_key` → `test_exception_propagates_to_error_messages` to verify new correct behavior.
- Updated `tests/test_planner.py::test_generate_plan_error_handling` to verify empty plan + translated error in `error_messages`.
- **Final test count: 369 passed, 0 failures** (362 baseline + 7 new).

### File List

- `utils/error_translation.py` (modified — added `openai.AuthenticationError` branch before `openai.APIError`)
- `pipeline/nodes/intent.py` (modified — fixed `except Exception` to call `translate_error()` and return `error_messages`)
- `pipeline/nodes/planner.py` (modified — fixed `except Exception` to call `translate_error()` and return `error_messages`)
- `tests/test_api_resilience.py` (new — 7 tests covering all 5 ACs)
- `tests/test_intent.py` (modified — updated `test_exception_returns_only_intent_key` to verify new correct error propagation behavior)
- `tests/test_planner.py` (modified — updated `test_generate_plan_error_handling` to verify empty plan + translated error_messages)
- `readme.md` (modified — typo fix: `c0mmand` → `command`)
- `_bmad-output/implementation-artifacts/6-2-llm-api-resilience-developer-error-reporting.md` (modified — story status, tasks, completion notes)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story status)

### Change Log

- 2026-03-13: Story 6.2 implemented — added `openai.AuthenticationError` to error taxonomy ("Add OPENAI_API_KEY to your .env file"); fixed `intent.py` and `planner.py` to propagate exceptions through `translate_error()` instead of silently swallowing them; created `tests/test_api_resilience.py` with 7 tests; 369 total tests passing.
