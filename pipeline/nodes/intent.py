# pipeline/nodes/intent.py
"""Intent classification node. Full implementation in Story 2.1.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def classify_intent(state: PipelineState) -> dict:
    """Classify user intent as 'report', 'qa', or 'chat'.

    Full implementation in Story 2.1 (natural language chat interface & intent classification).
    Returns only changed keys per LangGraph convention.
    """
    # TODO: implement in Story 2.1
    raise NotImplementedError("classify_intent() implemented in Story 2.1")
