# utils/error_translation.py
"""Error translation layer — all pipeline exceptions become plain-English messages here.

Full taxonomy implementation in Story 3.1 (error translation layer & no silent failures).
NOTE: Never import streamlit in this file.
"""


def translate_error(exception: Exception) -> str:
    """Translate an exception to a user-friendly plain-English message.

    Full error taxonomy implemented in Story 3.1:
      - openai.APIError       → "Unable to reach the AI service. Check your API key and connection."
      - openai.RateLimitError → "AI service rate limit reached. Please wait a moment and try again."
      - subprocess.TimeoutExpired → "Analysis took too long and was stopped. ..."
      - SyntaxError           → "Generated code had a syntax error — retrying with a corrected approach."
      - Allowlist violation   → "Generated code used a restricted operation — retrying with safer code."
      - All other Exception   → "An unexpected error occurred. Check the developer console for details."
    """
    # TODO: implement full taxonomy in Story 3.1
    return "An unexpected error occurred. Check the developer console for details."
