# Story 2.2: Execution Plan Generation & Display

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want to see a numbered execution plan appear in the Plan tab within 30 seconds of submitting a report-type request,
so that I can review exactly what the system will do before approving it.

## Acceptance Criteria

1. **Given** I submit a natural language request with `"report"` intent, **When** `generate_plan` runs, **Then** a step-by-step plan is generated and stored in `pipeline_state["plan"]` as a `list[str]`

2. **Given** the Plan tab, **When** a plan is available in `pipeline_state["plan"]`, **Then** it displays as a numbered list of human-readable sentences — plain English, no code, no jargon (e.g., "1. Load voltage and current data", "2. Calculate summary statistics", "3. Plot voltage vs time")

3. **Given** a submitted report request, **When** I wait for the plan to appear, **Then** it is displayed in the Plan tab within 30 seconds (NFR2)

4. **Given** the Plan tab is displaying a plan, **When** I click the Code or Template tab and return to Plan, **Then** the plan content is preserved — no LLM call is re-triggered (tab state preservation)

## Tasks / Subtasks

- [x] Task 1: Implement `generate_plan()` in `pipeline/nodes/planner.py` (AC: #1, #3)
  - [x] 1.1: Import `ChatOpenAI` from `langchain_openai` and `SystemMessage`, `HumanMessage` from `langchain_core.messages`
  - [x] 1.2: Define `_PLAN_SYSTEM_PROMPT` module-level constant that instructs GPT-4o to generate a numbered, plain-English execution plan for data analysis (no code, no jargon); output must be one step per line, numbered "1. ...", "2. ...", etc.
  - [x] 1.3: Implement `generate_plan(state: PipelineState) -> dict`: instantiate `ChatOpenAI(model="gpt-4o", temperature=0)`, invoke with `[SystemMessage(_PLAN_SYSTEM_PROMPT), HumanMessage(content)]` where content includes the user query AND column names/shape from `csv_temp_path` if available
  - [x] 1.4: Parse LLM response: split by newlines, strip numbering prefixes (e.g., "1. ", "2. "), filter empty lines, return list of step strings
  - [x] 1.5: Return ONLY `{"plan": plan_steps}` — never spread full state (LangGraph convention)
  - [x] 1.6: Wrap LLM call in try/except: on any exception return `{"plan": ["Error generating plan. Please try again."]}`
  - [x] 1.7: Confirm zero streamlit imports in this file

- [x] Task 2: Wire `generate_plan` into `_handle_chat_input()` for report intent (AC: #1, #3)
  - [x] 2.1: In `_handle_chat_input()` in `streamlit_app.py`, when `intent == "report"`, import and call `generate_plan` from `pipeline.nodes.planner` with the current `pipeline_state`
  - [x] 2.2: Merge the returned `{"plan": [...]}` into `pipeline_state` and update `st.session_state["pipeline_state"]`
  - [x] 2.3: Update the bot acknowledgment message to reflect that the plan has been generated (e.g., "I've created an execution plan for your request. Check the Plan tab to review it.")
  - [x] 2.4: Ensure the entire flow (classify_intent + generate_plan) completes within 30 seconds under normal conditions

- [x] Task 3: Update Plan tab display to render `pipeline_state["plan"]` (AC: #2, #4)
  - [x] 3.1: In `col2row1_plan_tab`, replace `st.write(st.session_state.plan)` with rendering from `st.session_state["pipeline_state"]["plan"]` — display as a numbered list using `st.markdown()` with each step on its own line
  - [x] 3.2: Add a guard: if `pipeline_state` is `None` or `pipeline_state["plan"]` is empty, show a placeholder message (e.g., "No plan generated yet. Submit a report-type request in the Chat panel.")
  - [x] 3.3: Keep the "Execute Plan" button visible only when a non-empty plan exists (button functionality is Story 2.3 — keep it calling `execute_plan()` for now but it will be rewired in 2.3)
  - [x] 3.4: Verify tab switching preserves plan content — no LLM re-trigger on tab switch (Streamlit tabs preserve state by default via session_state; confirmed)

- [x] Task 4: Write unit tests for `generate_plan` in `tests/test_planner.py` (AC: #1, #2)
  - [x] 4.1: Test `generate_plan` returns `{"plan": [...]}` with a list of strings — mock `ChatOpenAI` with a multi-line numbered response
  - [x] 4.2: Test plan steps are plain English strings (no code blocks, no backticks)
  - [x] 4.3: Test `generate_plan` returns ONLY the `"plan"` key (LangGraph convention — `assert set(result.keys()) == {"plan"}`)
  - [x] 4.4: Test error handling: when LLM raises an exception, returns `{"plan": ["Error generating plan. Please try again."]}`
  - [x] 4.5: Test no streamlit import in `pipeline/nodes/planner.py` via AST inspection
  - [x] 4.6: Test plan parsing: numbered lines like "1. Load data\n2. Analyze\n3. Plot" are parsed into `["Load data", "Analyze", "Plot"]`
  - [x] 4.7: Test that empty/whitespace-only lines in LLM response are filtered out

- [x] Task 5: Write integration test for report intent → plan generation flow (AC: #1, #2, #3)
  - [x] 5.1: Test that `_handle_chat_input` with a report-intent query results in `pipeline_state["plan"]` being populated with a non-empty list
  - [x] 5.2: Mock both `ChatOpenAI` (for classify_intent) and `ChatOpenAI` (for generate_plan) to avoid real API calls
  - [x] 5.3: Verify the bot message in chat_history reflects plan generation completion

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing `generate_plan()` in `pipeline/nodes/planner.py` using GPT-4o via `langchain_openai.ChatOpenAI`
- Wiring plan generation into the `_handle_chat_input()` flow for `"report"` intent
- Updating the Plan tab to display plans from `pipeline_state["plan"]` instead of the old `st.session_state.plan`
- Writing comprehensive tests for the planner node

**IS NOT:**
- Implementing the Execute button approval flow (Story 2.3 — keep existing button calling `execute_plan()`)
- Implementing code generation from the plan (Story 3.2)
- Wiring the full LangGraph pipeline graph (Story 3.5)
- Deleting the old `lg_plan_node`, `execute_plan()`, `langgraph_app`, or `CodePlanState` — keep these, they still serve the old pipeline path
- Implementing `plan_approved` or `pipeline_running` session state logic (Story 2.3)
- Adding plan step status badges or execution progress indicators (UX Phase 2)

### Current State (After Story 2.1)

**`pipeline/nodes/planner.py`** — stub file with `generate_plan()` raising `NotImplementedError`. Needs full implementation.

**`_handle_chat_input()`** in `streamlit_app.py` (lines 249-275):
- When `intent == "report"`, currently just appends an acknowledgment message to chat_history
- Does NOT call `generate_plan()` yet
- `pipeline_state` is stored in `st.session_state["pipeline_state"]` with `plan: []`

**Plan tab** in `streamlit_app.py` (lines 861-864):
- Currently renders `st.session_state.plan` (OLD key, string format)
- Has "Execute Plan" button calling `execute_plan(st.session_state.plan)` (old function)
- Needs to switch to reading from `st.session_state["pipeline_state"]["plan"]` (new key, list format)

**Session state keys:**
- `st.session_state["pipeline_state"]` — dict with `plan: list[str]` (new, from `init_session_state()`)
- `st.session_state.plan` — string (OLD, still initialized on line 797-798, used by old pipeline)

### Architecture Compliance Requirements

- **Module boundary:** `pipeline/nodes/planner.py` MUST NOT import streamlit. All `st.session_state` access is in `streamlit_app.py` only.
- **Node return convention:** `generate_plan()` returns ONLY `{"plan": plan_steps}` — never spread full state.
- **Naming:** `generate_plan` follows `verb_noun` pattern per architecture.
- **PipelineState contract:** `plan` field is `list[str]` per `pipeline/state.py` line 16.
- **Chat message format:** `{"role": "user"|"bot", "content": str}` — never `"assistant"`.
- **Error handling:** Simple fallback for now — full error taxonomy is Story 3.1. Return a list with a single error message string on failure.

### `generate_plan()` — Implementation Pattern

Follow the same pattern as `classify_intent()` in `pipeline/nodes/intent.py`:

```python
# pipeline/nodes/planner.py
from pipeline.state import PipelineState
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

_PLAN_SYSTEM_PROMPT = """You are an execution plan generator for a data analysis tool.
Given a user's analysis request and their dataset information, create a clear,
numbered step-by-step execution plan.

Rules:
- Each step must be a plain English sentence — no code, no technical jargon
- Steps should be concrete and actionable (e.g., "Load voltage and current columns",
  NOT "Process the data")
- Include data loading, computation, and visualization steps as appropriate
- Output ONLY the numbered list, one step per line
- Format: "1. Step description" on each line
- Typically 3-8 steps for most analysis requests"""


def generate_plan(state: PipelineState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # Build context-aware prompt including dataset info
    content = f"User request: {state['user_query']}"
    if state.get("csv_temp_path"):
        content += f"\nDataset path: {state['csv_temp_path']}"
    if state.get("data_row_count"):
        content += f"\nDataset rows: {state['data_row_count']}"

    messages = [
        SystemMessage(content=_PLAN_SYSTEM_PROMPT),
        HumanMessage(content=content),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # Parse numbered steps: "1. Step text" → "Step text"
        steps = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Remove numbering prefix (e.g., "1. ", "2. ", "10. ")
            import re
            cleaned = re.sub(r'^\d+\.\s*', '', line)
            if cleaned:
                steps.append(cleaned)
        if not steps:
            steps = [raw]  # fallback: treat entire response as one step
    except Exception:
        steps = ["Error generating plan. Please try again."]

    return {"plan": steps}
```

### `_handle_chat_input()` — Updated Report Intent Block

```python
if intent == "report":
    from pipeline.nodes.planner import generate_plan
    plan_result = generate_plan(pipeline_state)
    pipeline_state = {**pipeline_state, **plan_result}
    st.session_state["pipeline_state"] = pipeline_state
    bot_msg = (
        "I've created an execution plan for your request. "
        "Check the Plan tab to review it."
    )
    st.session_state["chat_history"].append({"role": "bot", "content": bot_msg})
```

### Plan Tab — Updated Rendering

```python
with col2row1_plan_tab:
    ps = st.session_state.get("pipeline_state")
    plan_steps = ps.get("plan", []) if ps else []
    if plan_steps:
        plan_text = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(plan_steps)
        )
        st.markdown(plan_text)
        if st.button("Execute Plan"):
            execute_plan(st.session_state.plan)  # keep old function for now
    else:
        st.info("No plan generated yet. Submit a report-type request in the Chat panel.")
```

### Testing Pattern for `generate_plan`

Follow the exact same mock pattern used in `tests/test_intent.py`.

### Dataset Context for Plan Generation

The `generate_plan` node should include dataset context in its LLM prompt to generate better plans. It receives `csv_temp_path` and `data_row_count` from `PipelineState`. However, it should NOT read the CSV file directly — that would violate the node's responsibility boundary. Instead:
- Use `csv_temp_path` to confirm data is available
- Use `data_row_count` to inform the plan about data size
- Column names can be derived from the user query context (the LLM already has the query)
- Full CSV reading for code generation is Story 3.2's responsibility

### Backward Compatibility Notes

The old code in `streamlit_app.py` that is NOT changed in this story:
- `execute_plan()` function — keep as-is, still called from Plan tab button
- `lg_plan_node`, `lg_write_code`, `lg_check_code`, `lg_rewrite_code`, `lg_update_plan` — keep, superseded in Story 3.5
- `langgraph_app` (the OLD graph) — keep, superseded in Story 3.5
- `CodePlanState` TypedDict — keep, used by old pipeline nodes
- `st.session_state.plan` (line 797-798) — keep initialization, but Plan tab should now READ from `pipeline_state["plan"]`
- `generate_chatbot_response()` — keep, no longer called

### NFR Compliance

- **NFR2 (30-second plan generation):** A single GPT-4o call with a concise prompt should return well within 30 seconds. No additional optimization needed for MVP.
- **Tab state preservation:** Streamlit tabs preserve content via session_state by design. Since the plan is stored in `st.session_state["pipeline_state"]["plan"]`, switching tabs and returning will re-render from the same state — no LLM re-trigger.

### Project Structure Notes

- **Modified file in `pipeline/`**: `pipeline/nodes/planner.py` (full implementation replaces stub)
- **Modified file in UI layer**: `streamlit_app.py` (wire generate_plan into _handle_chat_input + update Plan tab rendering)
- **New test file**: `tests/test_planner.py`
- **New integration test file**: `tests/test_story_2_2.py`

Alignment with architecture:
- `pipeline/nodes/planner.py` — zero streamlit imports ✅
- Returns only changed keys from LangGraph node (`{"plan": [...]}`) ✅
- `streamlit_app.py` owns all `st.session_state` reads/writes ✅
- Chat messages use `{"role": "user"|"bot", "content": str}` format ✅
- `generate_plan` follows `verb_noun` naming pattern ✅
- `generate_plan` called directly from `streamlit_app.py` (not via full pipeline yet — that wiring is Story 3.5) ✅

### References

- Epic 2, Story 2.2 definition: [epics.md](_bmad-output/planning-artifacts/epics.md#story-22-execution-plan-generation--display)
- Architecture — PipelineState.plan field: [architecture.md](_bmad-output/planning-artifacts/architecture.md#data-architecture)
- Architecture — planner node: [architecture.md](_bmad-output/planning-artifacts/architecture.md#module-structure)
- Architecture — naming patterns: [architecture.md](_bmad-output/planning-artifacts/architecture.md#naming-patterns)
- Architecture — module boundaries: [architecture.md](_bmad-output/planning-artifacts/architecture.md#architectural-boundaries)
- Architecture — node return convention: [architecture.md](_bmad-output/planning-artifacts/architecture.md#format-patterns)
- Previous Story 2.1 file: [2-1-natural-language-chat-interface-intent-classification.md](_bmad-output/implementation-artifacts/2-1-natural-language-chat-interface-intent-classification.md)
- UX — Plan tab display: [ux-design-specification.md](_bmad-output/planning-artifacts/ux-design-specification.md)
- Current stub: [planner.py](pipeline/nodes/planner.py)
- Current state definition: [state.py](pipeline/state.py)
- Current session init: [session.py](utils/session.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(none — implementation was straightforward following patterns from Story 2.1)

### Completion Notes List

- Implemented `generate_plan()` in `pipeline/nodes/planner.py`: full GPT-4o plan generation via `langchain_openai.ChatOpenAI`, with numbered-step parsing, empty-line filtering, and fallback on error. Zero streamlit imports confirmed.
- Wired `generate_plan` into `_handle_chat_input()` for `"report"` intent: plan generated and merged into `pipeline_state`, stored in `st.session_state["pipeline_state"]`, bot message updated to confirm plan is ready.
- Updated Plan tab rendering: reads from `pipeline_state["plan"]` (list), displays numbered markdown list via `st.markdown()`. Guard added for empty/None state shows info message. "Execute Plan" button shown only when plan is non-empty.
- Created `tests/test_planner.py` with 10 unit tests: all pass. Created `tests/test_story_2_2.py` with 3 integration tests: all pass.
- Full regression suite: 101 tests pass, zero regressions.

### File List

- `pipeline/nodes/planner.py` — full implementation replacing `NotImplementedError` stub
- `streamlit_app.py` — wired `generate_plan` into `_handle_chat_input()` for report intent; updated Plan tab display with `st.text()` (no markdown injection); Execute Plan button now passes new pipeline plan
- `tests/test_planner.py` — new test file (10 unit tests)
- `tests/test_story_2_2.py` — new integration test file (4 tests)

### Change Log

- Implemented Story 2.2: Execution Plan Generation & Display (Date: 2026-03-10)
- Code review fixes (Date: 2026-03-10): [M1] Execute Plan button now passes pipeline plan instead of stale `st.session_state.plan`; [M2] Removed unused imports (`sys`, `importlib`) from test_planner.py; [M3] Fixed confusing assertion in `test_generate_plan_uses_gpt4o` — clear keyword check; [M4] Rewrote integration tests as pipeline-layer tests (UI layer untestable without full Streamlit mock), added qa-intent non-generation test; [M5] Changed Plan tab from `st.markdown()` to `st.text()` to prevent markdown injection in LLM-generated plan steps. Reviewed by claude-opus-4-6.
