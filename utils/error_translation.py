# utils/error_translation.py
"""Error translation layer — all pipeline exceptions become plain-English messages here.

All modules must import translate_error from here and call it before displaying any
exception to the user. Never call st.error(str(e)) or st.error(repr(e)) directly.

NOTE: Never import streamlit in this file.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)


class AllowlistViolationError(Exception):
    """Raised by validate_code() in pipeline/nodes/validator.py when generated code
    contains an import or operation outside the permitted allowlist.
    Story 3.3 imports and raises this; Story 3.1 defines it here as the authoritative location.
    """
    pass


def translate_error(exception: Exception) -> str:
    """Translate an exception to a user-friendly plain-English message.

    Check order matters: AuthenticationError → RateLimitError → APIError (most
    specific first). All three are subclasses of APIError; if APIError is checked
    first it swallows the more specific matches.
    """
    try:
        return _translate_error_inner(exception)
    except Exception:
        logger.exception("translate_error itself failed for %r", exception)
        return "An unexpected error occurred. Check the developer console for details."


def _translate_error_inner(exception: Exception) -> str:
    """Inner dispatch — separated so translate_error can wrap with self-protection."""
    # Guard: openai may not be installed in test environments
    try:
        import openai
        # AuthenticationError (HTTP 401) MUST be checked before APIError because it is
        # a subclass of APIError — most specific first.
        if isinstance(exception, openai.AuthenticationError):
            return "Add OPENAI_API_KEY to your .env file"
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

    # File I/O errors — preserve diagnostic context for CSV upload and similar use cases
    if isinstance(exception, UnicodeDecodeError):
        return "File contains characters that couldn't be decoded. Try saving it with UTF-8 encoding."
    try:
        import pandas as pd
        if isinstance(exception, pd.errors.ParserError):
            return f"Could not parse the CSV file: {exception}"
    except ImportError:
        pass

    logger.error("Unhandled exception type %s: %s", type(exception).__name__, exception)
    return "An unexpected error occurred. Check the developer console for details."
