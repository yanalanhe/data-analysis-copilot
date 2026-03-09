# pipeline/state.py
"""PipelineState TypedDict — the typed data contract flowing through all LangGraph nodes.

This is the single source of truth for data shared between pipeline stages.
NOTE: Never import streamlit in this file.
"""
from typing import Literal
from typing_extensions import TypedDict


class PipelineState(TypedDict):
    user_query: str
    csv_temp_path: str           # nodes load CSV from file as needed; not passed as data
    data_row_count: int
    intent: Literal["report", "qa", "chat"]
    plan: list[str]
    generated_code: str
    validation_errors: list[str]
    execution_output: str
    execution_success: bool
    retry_count: int             # max 3 before adaptive replan (FR16)
    replan_triggered: bool
    error_messages: list[str]    # translated error history (FR29)
    report_charts: list[bytes]   # PNG bytes via BytesIO from subprocess (FR19)
    report_text: str             # written trend analysis (FR20)
    large_data_detected: bool
    large_data_message: str
    recovery_applied: str
