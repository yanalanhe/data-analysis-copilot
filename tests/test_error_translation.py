# tests/test_error_translation.py
"""Unit tests for error taxonomy mapping in utils/error_translation.py.

Tests all 6 error taxonomy cases from Story 3.1 acceptance criteria.
openai errors are guarded with try/except ImportError + pytest.skip so the suite
can run in environments where openai is not installed.
"""
import subprocess
import unittest.mock as mock
import pytest

from utils.error_translation import translate_error, AllowlistViolationError


# ─── Non-openai taxonomy cases (no import guard needed) ──────────────────────

def test_translate_syntax_error():
    """AC #4: SyntaxError → retrying message."""
    result = translate_error(SyntaxError("unexpected indent"))
    assert result == "Generated code had a syntax error — retrying with a corrected approach."


def test_translate_allowlist_violation():
    """AC #5: AllowlistViolationError → restricted operation message."""
    result = translate_error(AllowlistViolationError("import os not allowed"))
    assert result == "Generated code used a restricted operation — retrying with safer code."


def test_translate_subprocess_timeout():
    """AC #3: subprocess.TimeoutExpired → timeout message."""
    err = subprocess.TimeoutExpired(cmd="python script.py", timeout=60)
    result = translate_error(err)
    assert result == "Analysis took too long and was stopped. Try a simpler request or subset your data."


def test_translate_generic_value_error():
    """AC #6: generic ValueError → fallback message."""
    result = translate_error(ValueError("something internal went wrong"))
    assert result == "An unexpected error occurred. Check the developer console for details."


def test_translate_generic_runtime_error():
    """AC #6: generic RuntimeError → fallback message."""
    result = translate_error(RuntimeError("unexpected runtime problem"))
    assert result == "An unexpected error occurred. Check the developer console for details."


def test_translate_fallback_does_not_leak_exception_text():
    """Regression guard: fallback must never contain raw exception text (AC #6)."""
    exc = RuntimeError("secret internal detail xyz")
    result = translate_error(exc)
    assert "secret internal detail xyz" not in result
    assert "RuntimeError" not in result
    assert repr(exc) not in result


def test_translate_fallback_does_not_leak_exception_repr():
    """Regression guard: fallback must never contain repr(exception) content."""
    exc = ValueError("sensitive-token-abc123")
    result = translate_error(exc)
    assert "sensitive-token-abc123" not in result


# ─── File I/O error cases ────────────────────────────────────────────────────

def test_translate_unicode_decode_error():
    """UnicodeDecodeError → encoding hint message."""
    err = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    result = translate_error(err)
    assert result == "File contains characters that couldn't be decoded. Try saving it with UTF-8 encoding."


def test_translate_pandas_parser_error():
    """pd.errors.ParserError → message preserving parse context."""
    try:
        import pandas as pd
    except ImportError:
        pytest.skip("pandas not installed")

    err = pd.errors.ParserError("Error tokenizing data. C error: Expected 3 fields in line 4, saw 5")
    result = translate_error(err)
    assert "Could not parse the CSV file" in result
    assert "Expected 3 fields" in result


# ─── openai taxonomy cases (import-guarded) ──────────────────────────────────

def test_translate_openai_api_error():
    """AC #1: openai.APIError → AI service unreachable message."""
    try:
        import openai
    except ImportError:
        pytest.skip("openai not installed")

    err = openai.APIError(message="connection refused", request=mock.MagicMock(), body=None)
    result = translate_error(err)
    assert result == "Unable to reach the AI service. Check your API key and connection."


def test_translate_openai_rate_limit_error():
    """AC #2: openai.RateLimitError → rate limit message (NOT the generic APIError message)."""
    try:
        import openai
    except ImportError:
        pytest.skip("openai not installed")

    err = openai.RateLimitError(message="rate limit hit", response=mock.MagicMock(), body=None)
    result = translate_error(err)
    assert result == "AI service rate limit reached. Please wait a moment and try again."
    # Critical: must NOT fall through to the APIError branch (subclass ordering regression check)
    assert result != "Unable to reach the AI service. Check your API key and connection."


def test_rate_limit_error_is_subclass_of_api_error_ordering():
    """Verify subclass ordering: RateLimitError must be caught before APIError.

    RateLimitError is a subclass of APIError. If APIError is checked first,
    RateLimitError would incorrectly return the APIError message.
    This test confirms the correct message is returned.
    """
    try:
        import openai
    except ImportError:
        pytest.skip("openai not installed")

    rate_err = openai.RateLimitError(message="rate limit", response=mock.MagicMock(), body=None)
    api_err = openai.APIError(message="api error", request=mock.MagicMock(), body=None)

    assert translate_error(rate_err) == "AI service rate limit reached. Please wait a moment and try again."
    assert translate_error(api_err) == "Unable to reach the AI service. Check your API key and connection."
    # Messages must be different — confirms separate dispatch
    assert translate_error(rate_err) != translate_error(api_err)
