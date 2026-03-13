# tests/test_langsmith_integration.py
"""Tests for LangSmith tracing integration.

Covers Story 6.1 ACs #1–#6:
  AC #1: Traces visible in LangSmith when LANGSMITH_API_KEY + LANGCHAIN_TRACING_V2=true set
  AC #2: App works normally without LANGSMITH_API_KEY (no errors/warnings)
  AC #3: @traceable only on run_pipeline(); individual nodes NOT decorated
  AC #4: LangSmith connection failures silently caught — pipeline continues
  AC #5: .env.example documents all four required keys
  AC #6: No hardcoded API key values in pipeline/ or utils/ source

IMPORTANT: No real LangSmith API calls are made.
  - Structural checks use ast.parse on source files.
  - Functional checks mock compiled_graph.invoke.
  - All tests are pure unit/structural — no network calls.
"""
import ast
import os
import pathlib
import re
import unittest.mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_state(**overrides):
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "test",
        "csv_temp_path": None,
        "data_row_count": 0,
        "intent": "report",
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
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC #3: @_traceable decorator on run_pipeline() only
# ---------------------------------------------------------------------------

def test_run_pipeline_decorated_with_traceable():
    """run_pipeline() in pipeline/graph.py must be decorated with @_traceable."""
    src = pathlib.Path("pipeline/graph.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
            decorator_names = [ast.unparse(d) for d in node.decorator_list]
            assert any("_traceable" in d for d in decorator_names), (
                f"run_pipeline must be decorated with @_traceable. Found: {decorator_names}"
            )
            return
    pytest.fail("run_pipeline function not found in pipeline/graph.py")


def test_pipeline_nodes_not_decorated_with_traceable():
    """Individual pipeline nodes must NOT have @traceable — LangGraph traces them automatically."""
    node_dir = pathlib.Path("pipeline/nodes")
    for py_file in node_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for func in ast.walk(tree):
            if isinstance(func, ast.FunctionDef):
                for dec in func.decorator_list:
                    dec_str = ast.unparse(dec)
                    assert "traceable" not in dec_str.lower(), (
                        f"{py_file}::{func.name} must not use @traceable decorator; found: {dec_str}"
                    )


def test_traceable_import_fallback_present():
    """pipeline/graph.py must have an ImportError fallback for langsmith import."""
    src = pathlib.Path("pipeline/graph.py").read_text()
    # Check that the try/except ImportError fallback exists
    assert "except ImportError" in src, (
        "pipeline/graph.py must have an ImportError fallback for langsmith import"
    )
    assert "_traceable" in src, (
        "pipeline/graph.py must define _traceable as the local alias for traceable"
    )


# ---------------------------------------------------------------------------
# AC #2, #4: run_pipeline works without LangSmith key; silently handles failures
# ---------------------------------------------------------------------------

def test_run_pipeline_works_without_langsmith_key(monkeypatch):
    """run_pipeline() must succeed (AC #2) when LANGSMITH_API_KEY is absent."""
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    from pipeline.graph import run_pipeline

    state = _minimal_state()
    mock_result = {**state, "execution_success": True}
    with unittest.mock.patch("pipeline.graph.compiled_graph") as mock_graph:
        mock_graph.invoke.return_value = mock_result
        result = run_pipeline(state)
    assert result["execution_success"] is True
    assert result.get("error_messages", []) == []


def test_run_pipeline_silently_handles_pipeline_failure():
    """run_pipeline() must NOT raise on internal failure — returns translated error (AC #4)."""
    from pipeline.graph import run_pipeline

    state = _minimal_state()
    with unittest.mock.patch("pipeline.graph.compiled_graph") as mock_graph:
        mock_graph.invoke.side_effect = Exception("simulated connection error")
        result = run_pipeline(state)

    # Must NOT raise — must return a valid dict
    assert isinstance(result, dict)
    assert result.get("execution_success") is False

    # Error must be translated — NOT raw exception repr
    msgs = result.get("error_messages", [])
    assert len(msgs) > 0, "error_messages must contain at least one entry"
    for msg in msgs:
        assert "simulated connection error" not in msg, (
            "Raw exception text must not reach error_messages — must be translated"
        )
        assert "Exception(" not in msg, (
            "Raw Exception repr must not reach error_messages — must be translated"
        )


def test_run_pipeline_returns_dict_on_failure():
    """run_pipeline() return must always be a dict, never raise to the caller (AC #4)."""
    from pipeline.graph import run_pipeline

    state = _minimal_state()
    with unittest.mock.patch("pipeline.graph.compiled_graph") as mock_graph:
        mock_graph.invoke.side_effect = RuntimeError("unexpected error")
        result = run_pipeline(state)

    assert isinstance(result, dict), "run_pipeline must always return a dict, never raise"


# ---------------------------------------------------------------------------
# AC #5: .env.example documents all four required keys
# ---------------------------------------------------------------------------

def test_env_example_documents_required_keys():
    """.env.example must document all four LangSmith-related keys (AC #5)."""
    content = pathlib.Path(".env.example").read_text()
    required_keys = [
        "OPENAI_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_PROJECT",
    ]
    for key in required_keys:
        assert key in content, (
            f".env.example must document '{key}' — it is required or optional for tracing"
        )


# ---------------------------------------------------------------------------
# AC #6: No hardcoded API key values in production source
# ---------------------------------------------------------------------------

def test_no_hardcoded_openai_api_keys_in_pipeline():
    """No OpenAI-format API keys (sk-...) must be hardcoded in pipeline/ or utils/ (AC #6)."""
    sk_pattern = re.compile(r"sk-[A-Za-z0-9]{20,}")
    for path in [*pathlib.Path("pipeline").rglob("*.py"), *pathlib.Path("utils").rglob("*.py")]:
        content = path.read_text()
        matches = sk_pattern.findall(content)
        assert not matches, f"Possible hardcoded OpenAI key in {path}: {matches}"


def test_no_hardcoded_langsmith_api_keys_in_pipeline():
    """No LangSmith-format API keys (lsv2_...) must be hardcoded in pipeline/ or utils/ (AC #6)."""
    lsv_pattern = re.compile(r"lsv2_[A-Za-z0-9]{20,}")
    for path in [*pathlib.Path("pipeline").rglob("*.py"), *pathlib.Path("utils").rglob("*.py")]:
        content = path.read_text()
        matches = lsv_pattern.findall(content)
        assert not matches, f"Possible hardcoded LangSmith key in {path}: {matches}"


# ---------------------------------------------------------------------------
# AC #2, FR31: initialize_environment does NOT force LANGCHAIN_TRACING_V2
# ---------------------------------------------------------------------------

def test_initialize_environment_does_not_force_tracing():
    """initialize_environment() must not hardcode LANGCHAIN_TRACING_V2 (FR31, AC #2)."""
    src = pathlib.Path("streamlit_app.py").read_text(encoding="utf-8", errors="replace")
    # Locate the initialize_environment function body
    func_pattern = re.compile(
        r'def initialize_environment\(\).*?(?=\ndef |\nclass |\Z)',
        re.DOTALL,
    )
    match = func_pattern.search(src)
    assert match is not None, "initialize_environment() function not found in streamlit_app.py"
    func_body = match.group()

    # After the fix: must NOT force-set LANGCHAIN_TRACING_V2
    assert 'os.environ["LANGCHAIN_TRACING_V2"]' not in func_body, (
        "initialize_environment() must not hardcode LANGCHAIN_TRACING_V2 — "
        "tracing toggle must come from .env only (FR31)"
    )
    # Must NOT hardcode LANGCHAIN_PROJECT either
    assert 'os.environ["LANGCHAIN_PROJECT"]' not in func_body, (
        "initialize_environment() must not hardcode LANGCHAIN_PROJECT — must come from .env"
    )
    # Must NOT hardcode LANGCHAIN_ENDPOINT
    assert 'os.environ["LANGCHAIN_ENDPOINT"]' not in func_body, (
        "initialize_environment() must not hardcode LANGCHAIN_ENDPOINT — must come from .env"
    )
    # Must NOT manually copy LANGCHAIN_API_KEY from LANGSMITH_API_KEY
    assert 'os.environ["LANGCHAIN_API_KEY"]' not in func_body, (
        "initialize_environment() must not manually set LANGCHAIN_API_KEY — "
        "LangSmith reads LANGSMITH_API_KEY directly"
    )
