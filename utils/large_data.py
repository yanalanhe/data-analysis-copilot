# utils/large_data.py
"""Large data detection and uniform stride downsampling utilities.

detect_large_data: threshold check (Story 4.1).
apply_uniform_stride: uniform stride downsampling to target rows (Story 4.2).
NOTE: Never import streamlit in this file.
"""
import pandas as pd

LARGE_DATA_ROW_THRESHOLD = 100_000
LARGE_DATA_SIZE_THRESHOLD_MB = 20.0
DOWNSAMPLE_TARGET_ROWS = 10_000


def detect_large_data(row_count: int, size_mb: float) -> bool:
    """Return True if dataset exceeds the visualization size thresholds.

    Thresholds: >= 100,000 rows OR >= 20 MB combined size.
    Called on CSV upload before any pipeline execution (NFR5).
    """
    return row_count >= LARGE_DATA_ROW_THRESHOLD or size_mb >= LARGE_DATA_SIZE_THRESHOLD_MB


def apply_uniform_stride(
    df: pd.DataFrame, target_rows: int = DOWNSAMPLE_TARGET_ROWS
) -> pd.DataFrame:
    """Downsample df to target_rows using uniform stride sampling.

    If len(df) <= target_rows, returns df unchanged.
    Stride is calculated as len(df) // target_rows to ensure uniform coverage
    across the entire dataset (not just head).
    Result index is reset to start from 0.
    """
    if len(df) <= target_rows:
        return df
    stride = max(1, len(df) // target_rows)
    return df.iloc[::stride].head(target_rows).reset_index(drop=True)
