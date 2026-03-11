# tests/test_story_2_3.py
"""Tests for Story 2.3 — Plan Review & User-Triggered Execution.

Tests verify pipeline-layer invariants that support Story 2.3's AC:
- Pipeline nodes (classify_intent, generate_plan) never set plan_approved or
  pipeline_running — those flags are managed exclusively by the UI layer
- qa/chat intents leave pipeline_state["plan"] empty, which means the Plan tab
  guard hides the Execute button for those intents (AC #4, #5)

Note: streamlit is not installed in the test environment, so streamlit_app.py
cannot be imported or directly tested. The _handle_chat_input flag-reset
(Task 2) and Execute-button flag-setting (Task 1) are verified via code
inspection. The pipeline-layer tests here serve as regression guards ensuring
that no pipeline node accidentally introduces plan_approved/pipeline_running
into the state dict (which would break the UI-layer contract).
"""
from unittest.mock import MagicMock, patch

import pipeline.nodes.intent   # ensure in sys.modules before patching
import pipeline.nodes.planner  # ensure in sys.modules before patching


def _make_mock_response(content: str) -> MagicMock:
    r = MagicMock()
    r.content = content
    return r


def _make_full_state(query: str) -> dict:
    """Build a PipelineState-compatible dict for testing."""
    return {
        "user_query": query,
        "csv_temp_path": "",
        "data_row_count": 0,
        "intent": "chat",
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
        "large_data_detected": False,
        "large_data_message": "",
        "recovery_applied": "",
    }


# ---------------------------------------------------------------------------
# AC #2 / #3 — pipeline nodes must not introduce approval flags into state
# ---------------------------------------------------------------------------

def test_classify_intent_does_not_return_plan_approved():
    """classify_intent must not return plan_approved in its result dict.
    The approval flag lives in st.session_state only (AC #3)."""
    intent_response = _make_mock_response("report")

    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = intent_response
        mock_cls.return_value = mock_llm

        from pipeline.nodes.intent import classify_intent
        result = classify_intent(_make_full_state("plot voltage"))

    assert "plan_approved" not in result, \
        "classify_intent must not return plan_approved — it is UI-layer only"
    assert "pipeline_running" not in result, \
        "classify_intent must not return pipeline_running — it is UI-layer only"


def test_generate_plan_does_not_return_approval_flags():
    """generate_plan must not return plan_approved or pipeline_running.
    The approval flags live in st.session_state only (AC #3)."""
    plan_response = _make_mock_response("1. Load data\n2. Analyse\n3. Plot")

    with patch("pipeline.nodes.planner.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = plan_response
        mock_cls.return_value = mock_llm

        from pipeline.nodes.planner import generate_plan
        state = _make_full_state("create a chart of voltage vs time")
        state["intent"] = "report"
        result = generate_plan(state)

    assert "plan_approved" not in result, \
        "generate_plan must not return plan_approved — it is UI-layer only"
    assert "pipeline_running" not in result, \
        "generate_plan must not return pipeline_running — it is UI-layer only"
    assert set(result.keys()) == {"plan"}, \
        "generate_plan must return only the 'plan' key (LangGraph convention)"


# ---------------------------------------------------------------------------
# AC #4 — qa intent must not populate pipeline_state["plan"]
# ---------------------------------------------------------------------------

def test_qa_intent_does_not_populate_plan():
    """classify_intent returning 'qa' means plan stays empty in pipeline_state.
    The Plan tab guard hides the Execute button when plan is empty (AC #4)."""
    intent_response = _make_mock_response("qa")

    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = intent_response
        mock_cls.return_value = mock_llm

        from pipeline.nodes.intent import classify_intent
        state = _make_full_state("what is the max value in column A?")
        intent_result = classify_intent(state)
        state = {**state, **intent_result}

    assert intent_result["intent"] == "qa"
    assert state["plan"] == [], \
        "qa intent must not produce a plan — no Execute button should appear"


# ---------------------------------------------------------------------------
# AC #5 — chat intent must not populate pipeline_state["plan"]
# ---------------------------------------------------------------------------

def test_chat_intent_does_not_populate_plan():
    """classify_intent returning 'chat' means plan stays empty in pipeline_state.
    The Plan tab guard hides the Execute button when plan is empty (AC #5)."""
    intent_response = _make_mock_response("chat")

    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = intent_response
        mock_cls.return_value = mock_llm

        from pipeline.nodes.intent import classify_intent
        state = _make_full_state("hello there!")
        intent_result = classify_intent(state)
        state = {**state, **intent_result}

    assert intent_result["intent"] == "chat"
    assert state["plan"] == [], \
        "chat intent must not produce a plan — no Execute button should appear"
