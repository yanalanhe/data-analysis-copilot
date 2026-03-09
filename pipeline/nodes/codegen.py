# pipeline/nodes/codegen.py
"""Python code generation node. Full implementation in Story 3.2.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def generate_code(state: PipelineState) -> dict:
    """Generate Python analysis code from the approved execution plan.

    Full implementation in Story 3.2 (Python code generation from plan).
    System prompt must require plt.xlabel(), plt.ylabel(), plt.title(), plt.tight_layout()
    with descriptive labels (FR21). Returns only changed keys per LangGraph convention.
    """
    # TODO: implement in Story 3.2
    raise NotImplementedError("generate_code() implemented in Story 3.2")
