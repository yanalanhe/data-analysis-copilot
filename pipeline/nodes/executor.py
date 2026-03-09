# pipeline/nodes/executor.py
"""Subprocess sandbox execution node. Full implementation in Story 3.4.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def execute_code(state: PipelineState) -> dict:
    """Execute validated code in an isolated subprocess with 60s timeout.

    Full implementation in Story 3.4 (subprocess sandbox execution).
    Uses tempfile.mkdtemp() per session; cleans up after execution.
    Parses stdout for 'CHART:<base64_png>' lines → report_charts.
    Returns only changed keys per LangGraph convention.
    """
    # TODO: implement in Story 3.4
    raise NotImplementedError("execute_code() implemented in Story 3.4")
