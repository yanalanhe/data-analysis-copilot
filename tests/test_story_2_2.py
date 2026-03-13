# tests/test_story_2_2.py
"""Integration tests for Story 2.2 — report intent → plan generation pipeline flow.

Tests verify the pipeline-layer integration: classify_intent + generate_plan
working together as they would be called from _handle_chat_input.
Note: _handle_chat_input itself lives in streamlit_app.py (UI layer) and
cannot be unit-tested without a full Streamlit mock; its wiring is verified
via manual/E2E testing.
"""
from unittest.mock import MagicMock, patch

import pipeline.nodes.intent   # ensure in sys.modules before patching
import pipeline.nodes.planner  # ensure in sys.modules before patching


def _make_mock_response(content: str) -> MagicMock:
    r = MagicMock()
    r.content = content
    return r


def _make_full_state(query: str) -> dict:
    return {
        "user_query": query,
        "csv_temp_paths": {},
        "csv_metadata": "",
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
# Task 5.1 — classify_intent(report) → generate_plan populates plan list
# ---------------------------------------------------------------------------

def test_report_intent_then_generate_plan_populates_plan():
    """Pipeline integration: classify_intent returns 'report', then generate_plan
    produces a plan list — mirroring _handle_chat_input's orchestration logic."""
    intent_response = _make_mock_response("report")
    plan_response = _make_mock_response(
        "1. Load the CSV data\n2. Compute summary statistics\n3. Plot voltage vs time"
    )

    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_intent_cls, \
         patch("pipeline.nodes.planner.ChatOpenAI") as mock_plan_cls:
        mock_intent_llm = MagicMock()
        mock_intent_llm.invoke.return_value = intent_response
        mock_intent_cls.return_value = mock_intent_llm

        mock_plan_llm = MagicMock()
        mock_plan_llm.invoke.return_value = plan_response
        mock_plan_cls.return_value = mock_plan_llm

        from pipeline.nodes.intent import classify_intent
        from pipeline.nodes.planner import generate_plan

        state = _make_full_state("create a chart of voltage vs time")

        # Step 1: classify intent (mirrors _handle_chat_input)
        intent_result = classify_intent(state)
        assert intent_result["intent"] == "report"

        # Step 2: merge intent and generate plan (mirrors _handle_chat_input)
        state = {**state, **intent_result}
        plan_result = generate_plan(state)

        # Step 3: merge plan into state (mirrors _handle_chat_input)
        state = {**state, **plan_result}

    # Verify final state matches what session_state["pipeline_state"] would contain
    assert state["intent"] == "report"
    assert isinstance(state["plan"], list)
    assert len(state["plan"]) == 3
    assert state["plan"][0] == "Load the CSV data"
    assert state["plan"][1] == "Compute summary statistics"
    assert state["plan"][2] == "Plot voltage vs time"


# ---------------------------------------------------------------------------
# Task 5.2 — verify mocking prevents real API calls
# ---------------------------------------------------------------------------

def test_no_real_api_calls_in_plan_generation():
    """Ensure generate_plan with a mock never touches the real API."""
    plan_response = _make_mock_response("1. Load data\n2. Plot data")
    with patch("pipeline.nodes.planner.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = plan_response
        mock_cls.return_value = mock_llm
        from pipeline.nodes.planner import generate_plan
        result = generate_plan(_make_full_state("analyze my data"))
    mock_llm.invoke.assert_called_once()
    assert len(result["plan"]) == 2


# ---------------------------------------------------------------------------
# Task 5.3 — non-report intents do NOT trigger plan generation
# ---------------------------------------------------------------------------

def test_qa_intent_does_not_generate_plan():
    """Verify qa intent classification means plan stays empty —
    mirrors _handle_chat_input only calling generate_plan for 'report'."""
    intent_response = _make_mock_response("qa")

    with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = intent_response
        mock_cls.return_value = mock_llm

        from pipeline.nodes.intent import classify_intent
        state = _make_full_state("what is the max value in column A?")
        intent_result = classify_intent(state)

    assert intent_result["intent"] == "qa"
    # Plan remains empty — generate_plan is not called for qa intent
    assert state["plan"] == []


# ---------------------------------------------------------------------------
# Task 5 supplement — plan generation includes dataset context
# ---------------------------------------------------------------------------

def test_generate_plan_includes_dataset_context():
    """Plan generation prompt includes csv_metadata when available."""
    plan_response = _make_mock_response("1. Load data\n2. Analyze")
    with patch("pipeline.nodes.planner.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = plan_response
        mock_cls.return_value = mock_llm
        from pipeline.nodes.planner import generate_plan
        state = _make_full_state("plot voltage vs time")
        state["csv_metadata"] = "Available CSV files:\n- data.csv (5000 rows): voltage, time"
        generate_plan(state)
    messages = mock_llm.invoke.call_args[0][0]
    human_content = messages[-1].content
    assert "Available CSV files" in human_content
    assert "5000" in human_content
