# tests/test_intent.py
"""Unit tests for Story 2.1: classify_intent() in pipeline/nodes/intent.py.

Tests cover:
- Returns correct intent for report, qa, and chat queries
- Returns ONLY the "intent" key (LangGraph convention)
- Normalization: uppercase, whitespace trimming
- Fallback: unrecognized LLM response defaults to "chat"
- Fallback: LLM exception defaults to "chat"
- No streamlit import in pipeline/nodes/intent.py
"""
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pipeline.nodes.intent  # ensure module is importable for patch resolution

PROJECT_ROOT = Path(__file__).parent.parent


def _make_test_state(query: str) -> dict:
    """Build a minimal PipelineState dict for testing."""
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


def _make_mock_llm(response_content: str):
    """Return a mock ChatOpenAI instance that yields a fixed response."""
    mock_response = MagicMock()
    mock_response.content = response_content
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


class TestClassifyIntentReturnsCorrectIntent:
    def test_returns_report_intent_for_chart_query(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("report")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("create a chart of voltage vs time"))
        assert result["intent"] == "report"

    def test_returns_qa_intent_for_factual_query(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("qa")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("what is the max value in column A?"))
        assert result["intent"] == "qa"

    def test_returns_chat_intent_for_greeting(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("chat")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("hello"))
        assert result["intent"] == "chat"


class TestClassifyIntentOnlyReturnsIntentKey:
    def test_returns_only_intent_key(self):
        """LangGraph convention: node returns ONLY the keys it changed."""
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("report")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("create a chart"))
        assert set(result.keys()) == {"intent"}, (
            f"classify_intent must return only {{'intent'}} key, got {set(result.keys())}"
        )


class TestClassifyIntentNormalization:
    def test_uppercase_report_normalized(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("REPORT")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("create a chart"))
        assert result["intent"] == "report"

    def test_whitespace_qa_normalized(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("  qa  ")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("what is the max?"))
        assert result["intent"] == "qa"

    def test_partial_match_report_in_response(self):
        """If 'report' appears in raw response but not alone, still returns 'report'."""
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("this is a report intent")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("create a chart"))
        assert result["intent"] == "report"

    def test_partial_match_qa_in_response(self):
        """If 'qa' appears in raw response but not alone, still returns 'qa'."""
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("this is a qa question")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("what is the max?"))
        assert result["intent"] == "qa"

    def test_q_and_a_variant_normalized_to_qa(self):
        """'q&a' in raw response should also normalize to 'qa'."""
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("this is a q&a intent")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("how many rows are there?"))
        assert result["intent"] == "qa"


class TestClassifyIntentFallbacks:
    def test_unrecognized_response_defaults_to_chat(self):
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _make_mock_llm("I cannot classify this")
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("something weird"))
        assert result["intent"] == "chat"

    def test_exception_defaults_to_chat(self):
        """LLM exception must be caught and default to 'chat'."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API down")
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = mock_llm
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("hello"))
        assert result["intent"] == "chat"

    def test_exception_propagates_to_error_messages(self):
        """On exception, must return intent='chat' fallback AND error_messages with translated error."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API down")
        with patch("pipeline.nodes.intent.ChatOpenAI") as mock_cls:
            mock_cls.return_value = mock_llm
            from pipeline.nodes.intent import classify_intent
            result = classify_intent(_make_test_state("hello"))
        assert result["intent"] == "chat"
        assert "error_messages" in result, (
            "Intent node must propagate exceptions to error_messages (AC2, FR29)"
        )
        assert len(result["error_messages"]) > 0
        # Error must be translated — not raw repr
        assert "RuntimeError" not in result["error_messages"][0]


class TestClassifyIntentNoStreamlit:
    def test_no_streamlit_import_in_intent_module(self):
        """pipeline/nodes/intent.py must never import streamlit."""
        intent_file = PROJECT_ROOT / "pipeline" / "nodes" / "intent.py"
        source = intent_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "streamlit" not in alias.name, \
                        "pipeline/nodes/intent.py must not import streamlit"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "streamlit" not in node.module, \
                        "pipeline/nodes/intent.py must not import from streamlit"
