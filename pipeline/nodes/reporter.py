# pipeline/nodes/reporter.py
"""Report rendering node. Full implementation in Story 3.6.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def render_report(state: PipelineState) -> dict:
    """Finalise the pipeline state for report rendering in the UI.

    Full implementation in Story 3.6 (non-blocking execution panel & visual report rendering).
    Charts are rendered in the UI layer (streamlit_app.py) via st.image().
    Returns only changed keys per LangGraph convention.
    """
    # TODO: implement in Story 3.6
    raise NotImplementedError("render_report() implemented in Story 3.6")
