# Story 2.1: Natural Language Chat Interface & Intent Classification

Status: done

## Story

As an engineer,
I want to type analysis requests in a chat interface and have the system classify my intent,
so that the right pipeline path is triggered for my query type.

## Acceptance Criteria

1. **Given** the chat panel (top-left), **When** I type a message and press Enter, **Then** my message appears in the chat history with role `"user"`

2. **Given** a submitted query, **When** the system processes it, **Then** a response appears in the chat history with role `"bot"`

3. **Given** `st.session_state["chat_history"]`, **When** I interact with other panels or switch tabs, **Then** the chat history remains intact and fully visible

4. **Given** a submitted query with report intent (e.g., "create a chart of voltage vs time"), **When** `classify_intent` runs, **Then** `pipeline_state["intent"]` is set to `"report"`

5. **Given** a submitted query with Q&A intent (e.g., "what is the max value in column A?"), **When** `classify_intent` runs, **Then** `pipeline_state["intent"]` is set to `"qa"` and the system responds directly in the chat without generating a plan

6. **Given** a general conversation message (e.g., "hello"), **When** `classify_intent` runs, **Then** `pipeline_state["intent"]` is set to `"chat"` and the system responds directly in the chat with no plan or Execute button shown

## Tasks / Subtasks

- [x] Task 1: Implement `classify_intent()` in `pipeline/nodes/intent.py` (AC: #4, #5, #6)
  - [x] Import `ChatOpenAI` from `langchain_openai` and `SystemMessage`, `HumanMessage` from `langchain_core.messages`
  - [x] Define `_INTENT_SYSTEM_PROMPT` module-level constant that instructs GPT-4o to respond with exactly one word: `report`, `qa`, or `chat`
  - [x] Implement `classify_intent(state: PipelineState) -> dict`: instantiate `ChatOpenAI(model="gpt-4o", temperature=0)`, invoke with `[SystemMessage(_INTENT_SYSTEM_PROMPT), HumanMessage(state["user_query"])]`, parse and normalize the response
  - [x] Normalize LLM response: strip and lowercase; if in `("report", "qa", "chat")` use as-is; elif "report" in raw → "report"; elif "qa" in raw → "qa"; else → "chat" (default)
  - [x] Return ONLY `{"intent": intent_value}` — never spread full state (LangGraph convention)
  - [x] Wrap LLM call in try/except: on any exception default to `{"intent": "chat"}`
  - [x] Confirm zero streamlit imports in this file

- [x] Task 2: Add chat helper functions to `streamlit_app.py` (AC: #1, #2, #5, #6)
  - [x] Add `_make_initial_pipeline_state(user_input: str) -> dict` helper: builds a complete PipelineState dict with all 17 fields; sets `user_query=user_input`, `csv_temp_path` from `st.session_state.get("csv_temp_path") or ""`, `data_row_count` from `len(st.session_state.df)` if `"df"` in session_state else `0`, all other fields at zero/empty/False defaults
  - [x] Add `_generate_qa_response(user_input: str) -> str` helper: calls `openai_client.chat.completions.create` with a system prompt containing the dataset's shape, column names, and `df.head(3).to_string()` as context; returns the answer string; wraps in try/except returning a friendly fallback on failure
  - [x] Add `_generate_chat_response(user_input: str) -> str` helper: calls `openai_client.chat.completions.create` with a conversational system prompt describing what the copilot can do; returns the response string; wraps in try/except returning a friendly fallback on failure
  - [x] Add `_handle_chat_input(user_input: str) -> None` orchestrator: (1) builds initial state via `_make_initial_pipeline_state`, (2) calls `classify_intent` from `pipeline.nodes.intent`, (3) updates `st.session_state["pipeline_state"]` with intent, (4) routes by intent — "report": append acknowledgment bot message; "qa": call `_generate_qa_response` and append result; "chat": call `_generate_chat_response` and append result

- [x] Task 3: Replace old chat UI in `streamlit_app.py` col1row1 with new `chat_history`-based UI (AC: #1, #2, #3)
  - [x] In `col1row1`, replace `for message in st.session_state.messages:` rendering with `for msg in st.session_state["chat_history"]:` — use `msg["role"]` and `msg["content"]`; roles will be "user" and "bot"
  - [x] Update chat input handler: on user submit, append `{"role": "user", "content": user_input}` to `st.session_state["chat_history"]`, call `_handle_chat_input(user_input)`, then call `st.rerun()`
  - [x] Remove the call to `generate_chatbot_response()` from the chat input handler (keep the function definition in the file — it is NOT deleted yet, just no longer called from the new chat UI)
  - [x] Keep `if "messages" not in st.session_state: st.session_state.messages = []` guard elsewhere if needed for backward compat, but the chat rendering loop now reads from `chat_history` only
  - [x] Verify: chat title changed to `"Chat"` (was `"Chatbot"`)

- [x] Task 4: Write unit tests in `tests/test_intent.py` (AC: #4, #5, #6)
  - [x] Test `classify_intent` returns `{"intent": "report"}` for a report-style query — mock `ChatOpenAI` with response content `"report"`
  - [x] Test `classify_intent` returns `{"intent": "qa"}` for a Q&A-style query — mock `ChatOpenAI` with response content `"qa"`
  - [x] Test `classify_intent` returns `{"intent": "chat"}` for a greeting — mock `ChatOpenAI` with response content `"chat"`
  - [x] Test `classify_intent` returns ONLY the `"intent"` key (LangGraph convention — `assert set(result.keys()) == {"intent"}`)
  - [x] Test normalization: `"REPORT"` (uppercase) → `"report"`, `"  qa  "` (whitespace) → `"qa"`
  - [x] Test fallback: unrecognized LLM response (e.g., `"I cannot classify this"`) defaults to `"chat"`
  - [x] Test no streamlit import in `pipeline/nodes/intent.py` via AST inspection
  - [x] Test `classify_intent` defaults to `{"intent": "chat"}` when LLM raises an exception

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing `classify_intent()` in `pipeline/nodes/intent.py` using GPT-4o via `langchain_openai.ChatOpenAI`
- Replacing the OLD chat UI (which used `st.session_state.messages` + `generate_chatbot_response()`) with the new architecture-compliant chat UI (which uses `st.session_state["chat_history"]`)
- Adding direct LLM response helpers for `"qa"` and `"chat"` intents in `streamlit_app.py`

**IS NOT:**
- Implementing `generate_plan` (Story 2.2) — for "report" intent, just acknowledge in chat that a plan will be generated
- Implementing the Execute button or plan approval flow (Story 2.3)
- Implementing the full LangGraph pipeline wiring (Story 3.5)
- Changing the Plan tab content rendering (still shows `st.session_state.plan` — will be replaced in Story 2.2)
- Deleting `generate_chatbot_response()`, `execute_plan()`, `lg_plan_node`, `langgraph_app` — keep these, just no longer called from the new chat UI

### Current Chat UI State (After Story 1.3)

The existing `col1row1` block renders chat using `st.session_state.messages` (role: "user"/"assistant"):

```python
# CURRENT — OLD approach (to be replaced in this story)
if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with chat_history_container.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("What is up?")
if user_input:
    with chat_history_container.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    with chat_history_container.chat_message("assistant"):
        response = generate_chatbot_response(openai_client, st.session_state, user_input)
    st.session_state.messages.append({"role": "assistant", "content": response})
```

### New Chat UI (After This Story)

```python
# NEW — Architecture-compliant approach using chat_history
# chat_history is initialized by init_session_state() at app startup
# format: [{"role": "user" | "bot", "content": str}, ...]

for msg in st.session_state["chat_history"]:
    with chat_history_container.chat_message(msg["role"]):
        st.markdown(msg["content"])

with st.container():
    user_input = st.chat_input("Ask something about your data...")
    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        _handle_chat_input(user_input)
        st.rerun()
```

### `_make_initial_pipeline_state()` — All 17 PipelineState Fields

Must populate ALL fields (TypedDict for type safety, even though Python doesn't enforce at runtime):

```python
def _make_initial_pipeline_state(user_input: str) -> dict:
    return {
        "user_query": user_input,
        "csv_temp_path": st.session_state.get("csv_temp_path") or "",
        "data_row_count": len(st.session_state.df) if "df" in st.session_state else 0,
        "intent": "chat",           # will be updated after classify_intent
        "plan": [],
        "generated_code": "",
        "validation_errors": [],
        "execution_output": "",
        "execution_success": False,
        "retry_count": 0,
        "replan_triggered": False,
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
        "large_data_detected": bool(st.session_state.get("large_data_detected", False)),
        "large_data_message": st.session_state.get("large_data_message", ""),
        "recovery_applied": st.session_state.get("recovery_applied", ""),
    }
```

### `_handle_chat_input()` — Intent Routing Logic

```python
def _handle_chat_input(user_input: str) -> None:
    from pipeline.nodes.intent import classify_intent

    pipeline_state = _make_initial_pipeline_state(user_input)

    try:
        intent_result = classify_intent(pipeline_state)
        intent = intent_result.get("intent", "chat")
    except Exception:
        intent = "chat"

    pipeline_state = {**pipeline_state, "intent": intent}
    st.session_state["pipeline_state"] = pipeline_state

    if intent == "report":
        bot_msg = (
            "Got it! I'll generate an execution plan for your request. "
            "It will appear in the Plan tab shortly."
        )
        st.session_state["chat_history"].append({"role": "bot", "content": bot_msg})
    elif intent == "qa":
        answer = _generate_qa_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": answer})
    else:  # "chat"
        response = _generate_chat_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": response})
```

### `classify_intent()` — Node Implementation Pattern

```python
# pipeline/nodes/intent.py
from pipeline.state import PipelineState
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for a data analysis tool.
Classify the user's message into exactly one of these three categories:
- "report": The user wants to create a chart, visualization, analysis report, or any
  computation/aggregation of data (e.g., "create a chart of X vs Y", "analyze column X",
  "calculate correlation", "show trends in")
- "qa": The user wants a direct factual answer about the data without a full report
  (e.g., "what is the max value?", "how many rows?", "what is the average of column B?")
- "chat": General conversation, capability questions, or greetings
  (e.g., "hello", "what can you do?", "thank you")

Respond with ONLY one word: report, qa, or chat. No explanation, no punctuation."""


def classify_intent(state: PipelineState) -> dict:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    messages = [
        SystemMessage(content=_INTENT_SYSTEM_PROMPT),
        HumanMessage(content=state["user_query"]),
    ]
    try:
        response = llm.invoke(messages)
        raw = response.content.strip().lower()
        if raw in ("report", "qa", "chat"):
            intent = raw
        elif "report" in raw:
            intent = "report"
        elif "qa" in raw or "q&a" in raw:
            intent = "qa"
        else:
            intent = "chat"
    except Exception:
        intent = "chat"

    return {"intent": intent}
```

### Chat Message Format — Architecture Rule

Always use this EXACT shape (per architecture.md):
```python
{"role": "user" | "bot", "content": str}
# WRONG:
{"role": "assistant", ...}  # ❌ old Streamlit role name
{"sender": "user", ...}     # ❌
```

Note: Streamlit's `st.chat_message("bot")` renders with a generic bot avatar. This is intentional.

### Backward Compatibility Notes

The old code in `streamlit_app.py` that is NOT changed in this story:
- `generate_chatbot_response()` — keep function, no longer called from chat UI
- `execute_plan()` — keep as-is, still called from Plan tab "Execute Plan" button
- `lg_plan_node`, `lg_write_code`, `lg_check_code`, `lg_rewrite_code`, `lg_update_plan` — keep, will be superseded in Story 3.5
- `langgraph_app` (the OLD graph) — keep, will be superseded in Story 3.5
- `CodePlanState` TypedDict — keep, used by old pipeline nodes
- `st.session_state.messages` — still initialized via the guard elsewhere; no longer rendered in chat panel

After Story 2.1, the Plan tab still shows `st.session_state.plan` (will be empty for new "report" queries until Story 2.2 wires plan generation). The "Execute Plan" button still works for any plan that was previously stored via the old path. This is acceptable — Story 2.2 will populate `plan` via the new `generate_plan` node.

### `_generate_qa_response()` and `_generate_chat_response()` — LLM Error Handling

Both helpers must wrap `openai_client.chat.completions.create` in try/except and return a friendly message on failure. Do NOT raise or call `translate_error()` directly here — the full error taxonomy is Story 3.1. A simple fallback string is sufficient:
```python
except Exception:
    return "I'm unable to respond right now. Please check your connection and try again."
```

### Testing Pattern for `classify_intent`

Tests must mock `ChatOpenAI` to avoid real API calls:
```python
from unittest.mock import MagicMock, patch

def test_returns_report_intent():
    mock_response = MagicMock()
    mock_response.content = "report"
    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_llm_class:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        from pipeline.nodes.intent import classify_intent
        result = classify_intent(_make_test_state("create a chart of voltage vs time"))
    assert result["intent"] == "report"
```

Important: The import of `classify_intent` inside the `with patch(...)` block ensures the mock is in scope during the call. Alternatively, patch at module level and import at top.

### Project Structure Notes

- **Only modified file in `pipeline/`**: `pipeline/nodes/intent.py` (full implementation replaces stub)
- **Modified file in UI layer**: `streamlit_app.py` (new helpers + chat panel replacement in col1row1)
- **New test file**: `tests/test_intent.py`
- **No new files in `utils/` or `pipeline/`** — only the existing stub is filled in

Alignment with architecture:
- `pipeline/nodes/intent.py` — zero streamlit imports ✅
- Returns only changed keys from LangGraph node ✅
- `streamlit_app.py` owns all `st.session_state` reads/writes ✅
- Chat messages use `{"role": "user"|"bot", "content": str}` format ✅
- `classify_intent` called directly from `streamlit_app.py` (not via full pipeline yet — that wiring is Story 3.5) ✅

### References

- Epic 2, Story 2.1 definition: [epics.md](_bmad-output/planning-artifacts/epics.md#story-21-natural-language-chat-interface--intent-classification)
- Architecture — chat message format: [architecture.md](_bmad-output/planning-artifacts/architecture.md#format-patterns)
- Architecture — session state schema: [architecture.md](_bmad-output/planning-artifacts/architecture.md#data-architecture)
- Architecture — naming patterns (snake_case, verb_noun nodes): [architecture.md](_bmad-output/planning-artifacts/architecture.md#naming-patterns)
- Architecture — module boundaries (no streamlit in pipeline/): [architecture.md](_bmad-output/planning-artifacts/architecture.md#architectural-boundaries)
- Architecture — LangGraph node return convention (only changed keys): [architecture.md](_bmad-output/planning-artifacts/architecture.md#format-patterns)
- Previous Story 1.3 learnings: [1-3-four-panel-layout-csv-upload-with-editable-data-table.md](_bmad-output/implementation-artifacts/1-3-four-panel-layout-csv-upload-with-editable-data-table.md)
- `utils/session.py` — `init_session_state()` already initializes `chat_history: []`: [utils/session.py](utils/session.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Tests initially failed because `pipeline.nodes.intent` wasn't imported before patching — fixed by adding `import pipeline.nodes.intent` at test module level to ensure it's in `sys.modules` before `mock.patch` resolves the dotted path.

### Completion Notes List

- Implemented `classify_intent()` in `pipeline/nodes/intent.py`: full GPT-4o intent classification via `langchain_openai.ChatOpenAI`, with normalization and fallback logic. Zero streamlit imports confirmed.
- Added four helpers to `streamlit_app.py`: `_make_initial_pipeline_state`, `_generate_qa_response`, `_generate_chat_response`, `_handle_chat_input`. All follow architecture patterns.
- Replaced old `st.session_state.messages`-based chat rendering with `st.session_state["chat_history"]`-based rendering in `col1row1`. Title changed from "Chatbot" to "Chat". `generate_chatbot_response()` kept but no longer called.
- Created `tests/test_intent.py` with 12 unit tests covering all subtasks. All 74 tests pass with zero regressions.

### File List

- `pipeline/nodes/intent.py` — replaced stub with full implementation
- `streamlit_app.py` — added 4 chat helpers + replaced chat UI in col1row1
- `tests/test_intent.py` — new test file (13 tests)

### Change Log

- Implemented Story 2.1: Natural Language Chat Interface & Intent Classification (Date: 2026-03-09)
- Code review fixes (Date: 2026-03-10): [H1] Added missing "q&a" normalization test; [M1] Added conversation history to `_generate_chat_response` for multi-turn context; [M2] Fixed `st.session_state.df` dot-access anti-pattern to bracket notation; [M3] Added column limiting (30 cols) in `_generate_qa_response` to prevent oversized LLM prompts; [M4] Updated File List. Reviewed by claude-opus-4-6.
