# utils/session.py
"""Session state initialisation helpers.

This is the ONLY file in utils/ that may import streamlit.
All st.session_state keys for the new pipeline are defined here.
"""
import streamlit as st

from utils.templates import load_templates


def init_session_state() -> None:
    """Initialize all new-pipeline st.session_state keys with their defaults.

    Idempotent: only sets keys that are not already present.
    Must be called on every Streamlit rerun from streamlit_app.py.
    Does NOT interfere with existing session keys used by the brownfield pipeline
    (df, openai_model, messages, plan, code, thoughtflow, current_user_input,
    formatted_output, table_changed, langgraph_initialized).
    """
    defaults = {
        "uploaded_dfs": {},
        "csv_temp_paths": {},
        "chat_history": [],
        "pipeline_state": None,
        "pipeline_running": False,
        "plan_approved": False,
        "active_tab": "plan",
        "active_template": None,
        "large_data_detected": False,   # Story 4.1: set True on upload when threshold exceeded
        "large_data_message": "",       # Story 4.1: human-readable message for inline warning
        "recovery_applied": "",         # Story 4.2: "" = none, "downsampled" = auto-downsampled
        "show_save_template_form": False,  # Story 5.3: True = inline name form showing in Plan tab
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    # Lazy-load templates only when key is missing (avoids disk I/O on every rerun)
    if "saved_templates" not in st.session_state:
        st.session_state["saved_templates"] = _safe_load_templates()


def _safe_load_templates() -> list:
    """Load saved templates from disk, returning empty list on any failure."""
    try:
        return load_templates()
    except Exception:
        return []
