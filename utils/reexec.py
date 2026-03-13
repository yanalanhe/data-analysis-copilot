# utils/reexec.py
"""Re-execution state builder for the Code tab's manual Re-run feature (Story 5.2).

Extracted from streamlit_app.py so tests can import directly without triggering
Streamlit module-level initialization.

NOTE: Never import streamlit in this file.
"""

# Keys from PipelineState that are preserved (not reset) during re-execution.
_PRESERVED_KEYS = frozenset({
    "user_query",
    "csv_temp_path",
    "data_row_count",
    "intent",
    "plan",
    "large_data_detected",
    "large_data_message",
    "recovery_applied",
})


def build_reexec_state(ps: dict, edited_code: str) -> dict:
    """Build a clean re-execution state from existing pipeline state with edited code.

    Preserves only the keys in _PRESERVED_KEYS from the original state.
    Resets all execution-related fields to clean initial values.
    Overrides generated_code with edited_code (falls back to original if None).

    Args:
        ps: The current pipeline_state dict.
        edited_code: The user's edited code from st_ace. May be None on initial
            render before user interaction — falls back to original generated_code.

    Returns:
        A new dict suitable for passing to validate_code_node / execute_code.
    """
    # Defensive: st_ace returns None on initial render before user interaction.
    if edited_code is None:
        edited_code = ps.get("generated_code", "")

    preserved = {k: ps[k] for k in _PRESERVED_KEYS if k in ps}
    return {
        **preserved,
        "generated_code": edited_code,
        "validation_errors": [],
        "retry_count": 0,
        "replan_triggered": False,
        "execution_success": False,
        "execution_output": "",
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
    }
