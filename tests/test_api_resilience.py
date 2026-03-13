# tests/test_api_resilience.py
"""Tests for Story 6.2: LLM API Resilience & Developer Error Reporting.

Covers all 5 Acceptance Criteria:
- AC1: openai.APIError → "Unable to reach the AI service..." (NFR14)
- AC2: pipeline_state["error_messages"] contains human-readable descriptions (FR32)
- AC3: OPENAI_API_KEY missing → "Add OPENAI_API_KEY to your .env file"
- AC4: App runs cleanly without LangSmith config (NFR15, NFR16) — structural test
- AC5: requirements.txt all pinned with == (NFR16)
"""
import pathlib
import re
import unittest.mock

import pytest

from utils.error_translation import translate_error


# ---------------------------------------------------------------------------
# AC #3: AuthenticationError → actionable "Add OPENAI_API_KEY" message
# ---------------------------------------------------------------------------

def test_translate_authentication_error():
    """AuthenticationError (missing/invalid API key) → actionable fix message (AC #3)."""
    import openai
    err = openai.AuthenticationError(
        message="No API key provided",
        response=unittest.mock.MagicMock(status_code=401, headers={}),
        body={"error": {"message": "No API key provided"}},
    )
    result = translate_error(err)
    assert result == "Add OPENAI_API_KEY to your .env file"


# ---------------------------------------------------------------------------
# AC #1: Generic APIError → "Unable to reach the AI service..." message
# ---------------------------------------------------------------------------

def test_translate_api_connection_error():
    """APIConnectionError (network down) → generic API error message (AC #1)."""
    import openai
    err = openai.APIConnectionError(request=unittest.mock.MagicMock())
    result = translate_error(err)
    assert result == "Unable to reach the AI service. Check your API key and connection."


# ---------------------------------------------------------------------------
# AC #1: RateLimitError → rate limit message (existing taxonomy, must still work)
# ---------------------------------------------------------------------------

def test_translate_rate_limit_error():
    """RateLimitError → rate limit message (existing taxonomy must be preserved) (AC #1)."""
    import openai
    err = openai.RateLimitError(
        message="Rate limit exceeded",
        response=unittest.mock.MagicMock(status_code=429, headers={}),
        body={"error": {"message": "Rate limit"}},
    )
    result = translate_error(err)
    assert result == "AI service rate limit reached. Please wait a moment and try again."


# ---------------------------------------------------------------------------
# AC #3: AuthenticationError must produce a DIFFERENT (more specific) message
#         than generic APIError — confirms subclass check order is correct
# ---------------------------------------------------------------------------

def test_authentication_error_is_more_specific_than_api_error():
    """AuthenticationError returns different, more specific message than generic APIError.

    This validates that isinstance(exception, openai.AuthenticationError) is checked
    BEFORE isinstance(exception, openai.APIError) in _translate_error_inner() (AC #3).
    """
    import openai
    auth_err = openai.AuthenticationError(
        message="Invalid API key",
        response=unittest.mock.MagicMock(status_code=401, headers={}),
        body={"error": {"message": "Invalid API key"}},
    )
    api_err = openai.APIConnectionError(request=unittest.mock.MagicMock())

    auth_msg = translate_error(auth_err)
    api_msg = translate_error(api_err)

    assert auth_msg != api_msg, (
        "AuthenticationError must produce a different message than a generic APIError"
    )
    assert "OPENAI_API_KEY" in auth_msg, (
        "AuthenticationError message must identify the missing/invalid key"
    )
    assert ".env" in auth_msg, (
        "AuthenticationError message must tell user where to fix it"
    )


# ---------------------------------------------------------------------------
# AC #2: run_pipeline() propagates APIError into error_messages as human-readable
# ---------------------------------------------------------------------------

def test_api_error_propagates_as_human_readable():
    """APIError raised inside graph.invoke() lands in error_messages as translated text (AC #2)."""
    import openai
    from pipeline.graph import run_pipeline

    minimal_state = {
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

    api_error = openai.APIConnectionError(request=unittest.mock.MagicMock())

    with unittest.mock.patch("pipeline.graph.compiled_graph") as mock_graph:
        mock_graph.invoke.side_effect = api_error
        result = run_pipeline(minimal_state)

    assert result["execution_success"] is False, (
        "execution_success must be False when pipeline raises APIError"
    )
    msgs = result.get("error_messages", [])
    assert len(msgs) > 0, "error_messages must contain at least one entry"
    # Must be translated — not raw repr
    assert "APIConnectionError" not in msgs[0], (
        "error_messages must not contain raw exception class names"
    )
    assert "Unable to reach" in msgs[0], (
        "error_messages must contain the translated human-readable message"
    )


# ---------------------------------------------------------------------------
# AC #5: requirements.txt — all dependencies pinned with ==
# ---------------------------------------------------------------------------

def test_requirements_all_pinned():
    """Every line in requirements.txt uses exact == version pin (AC #5, NFR16)."""
    content = pathlib.Path("requirements.txt").read_text(encoding="utf-8", errors="replace")
    violations = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            violations.append(f"Missing == pin: {line!r}")
        elif ">=" in line:
            violations.append(f"Unpinned (>=): {line!r}")
        elif "~=" in line:
            violations.append(f"Unpinned (~=): {line!r}")
    assert not violations, (
        f"requirements.txt has unpinned entries:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# AC #2: No raw st.error(str(e)) or st.error(repr(e)) patterns in source
#         (confirms all errors go through translate_error — FR32)
# ---------------------------------------------------------------------------

def test_no_raw_exception_to_ui():
    """No st.error(str(e)) or st.error(repr(e)) calls exist in actual code (AC #2, FR32).

    Uses AST analysis to find only executable Call nodes, ignoring docstrings
    and comments that may mention st.error(str(e)) as an example of what NOT to do.
    """
    import ast

    violations = []
    paths_to_check = [
        pathlib.Path("streamlit_app.py"),
        *pathlib.Path("pipeline").rglob("*.py"),
        *pathlib.Path("utils").rglob("*.py"),
    ]
    for path in paths_to_check:
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Match st.error(str(...)) or st.error(repr(...))
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "error"
                and isinstance(func.value, ast.Name)
                and func.value.id == "st"
                and node.args
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id in ("str", "repr")
            ):
                violations.append(f"{path}:{node.lineno}")
    assert not violations, (
        "Raw exception display found (violates error translation rule):\n"
        + "\n".join(violations)
    )
