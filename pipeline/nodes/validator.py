# pipeline/nodes/validator.py
"""AST allowlist code validator node. Full implementation in Story 3.3.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState


def validate_code(state: PipelineState) -> dict:
    """Validate generated code for syntax errors and unsafe operations.

    Full implementation in Story 3.3 (AST allowlist code validator).
    Returns tuple (is_valid: bool, errors: list[str]) via state dict.
    Returns only changed keys per LangGraph convention.

    Permitted imports: pandas, numpy, matplotlib, matplotlib.pyplot, math,
    statistics, datetime, collections, itertools, io, base64.
    """
    # TODO: implement in Story 3.3
    raise NotImplementedError("validate_code() implemented in Story 3.3")
