# tests/test_code_viewer.py
"""Unit tests for the Code tab logic in streamlit_app.py (Story 5.1).

Tests the get_code_for_display helper that mirrors the Code tab session-state
reading pattern (sync: streamlit_app.py col2row1_code_tab block):

    ps = st.session_state.get("pipeline_state")
    generated_code = ps.get("generated_code", "") if isinstance(ps, dict) else ""
"""


def get_code_for_display(pipeline_state) -> str:
    """Pure helper that mirrors the Code tab logic in streamlit_app.py.

    Extracts generated_code from pipeline_state dict.
    Returns empty string when pipeline_state is None, not a dict, or missing the field.

    IMPORTANT: Keep in sync with streamlit_app.py col2row1_code_tab block.
    """
    if not isinstance(pipeline_state, dict):
        return ""
    return pipeline_state.get("generated_code", "")


class TestGetCodeForDisplay:
    """Tests for the Code tab session-state reading logic (AC #1, #2, #3)."""

    def test_pipeline_state_none_returns_empty_string(self):
        """Task 2.2: pipeline_state is None → generated_code resolves to ''."""
        assert get_code_for_display(None) == ""

    def test_pipeline_state_empty_dict_returns_empty_string(self):
        """Task 2.3: pipeline_state is {} (no generated_code key) → '' returned."""
        assert get_code_for_display({}) == ""

    def test_pipeline_state_with_empty_generated_code_returns_empty_string(self):
        """Task 2.4: pipeline_state['generated_code'] == '' → '' returned."""
        assert get_code_for_display({"generated_code": ""}) == ""

    def test_pipeline_state_with_valid_code_returns_code(self):
        """Task 2.5: valid Python code in generated_code → non-empty string returned."""
        code = "import pandas as pd\ndf.describe()"
        result = get_code_for_display({"generated_code": code})
        assert result == code
        assert len(result) > 0

    def test_pipeline_state_with_extra_fields_returns_only_generated_code(self):
        """Extra fields in pipeline_state do not interfere."""
        code = "print('hello')"
        ps = {
            "generated_code": code,
            "plan": "some plan",
            "error": None,
        }
        assert get_code_for_display(ps) == code

    def test_non_dict_pipeline_state_returns_empty_string(self):
        """Non-dict truthy values (string, list, int) return '' safely."""
        assert get_code_for_display("not a dict") == ""
        assert get_code_for_display([1, 2, 3]) == ""
        assert get_code_for_display(42) == ""
