# pipeline/nodes/error_handler.py
"""Error handler node for retry count management.

Implements handle_error(state: PipelineState) -> dict, which increments
retry_count and sets replan_triggered when the retry threshold is reached.

NOTE: handle_error is implemented here as a utility node.
In the Story 3.5 graph, retry_count is incremented directly in execute_code
on failure paths, and route_after_execution routes based on the updated count.
handle_error is available for use in alternative graph topologies or future stories.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def handle_error(state: PipelineState) -> dict:
    """Increment retry_count and set replan_triggered at threshold.

    Appends a human-readable retry or replan message to error_messages.
    Returns only changed keys per LangGraph convention.

    Args:
        state: Current PipelineState with retry_count and error_messages.

    Returns:
        dict with updated retry_count, replan_triggered, and error_messages.
    """
    current_retry = state.get("retry_count", 0)
    new_retry = current_retry + 1
    replan = new_retry >= 3

    existing_errors = list(state.get("error_messages", []))

    if replan:
        msg = "Maximum retries reached — adaptively replanning the analysis approach."
    else:
        msg = f"Retrying code generation (attempt {new_retry}/3)."

    return {
        "retry_count": new_retry,
        "replan_triggered": replan,
        "error_messages": existing_errors + [msg],
    }
