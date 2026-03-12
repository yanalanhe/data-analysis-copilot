# pipeline/nodes/reporter.py
"""Report rendering node.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def render_report(state: PipelineState) -> dict:
    """Finalise the pipeline state for report rendering in the UI.

    Charts (report_charts) and text (report_text) are already populated in
    state by execute_code (Story 3.4). This node is the named terminal node
    that signals pipeline completion — actual rendering via st.image() and
    st.markdown() happens in streamlit_app.py within the @st.fragment panel.

    Returns:
        Empty dict — no state mutations; all output fields are already set
        by execute_code. Returning {} is valid LangGraph convention for a
        node that makes no state changes.
    """
    return {}
