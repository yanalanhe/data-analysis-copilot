# utils/large_data.py
"""Large data detection and uniform stride downsampling utilities.

Full implementation in Stories 4.1 (detect_large_data) and 4.2 (apply_uniform_stride).
NOTE: Never import streamlit in this file.
"""
import pandas as pd

LARGE_DATA_ROW_THRESHOLD = 100_000
LARGE_DATA_SIZE_THRESHOLD_MB = 20.0
DOWNSAMPLE_TARGET_ROWS = 10_000


def detect_large_data(row_count: int, size_mb: float) -> bool:
    """Return True if dataset exceeds the visualization size thresholds.

    Thresholds: >= 100,000 rows OR >= 20 MB combined size.
    Full implementation in Story 4.1 (large dataset detection & inline warning).
    """
    # TODO: implement in Story 4.1
    return False


def apply_uniform_stride(
    df: pd.DataFrame, target_rows: int = DOWNSAMPLE_TARGET_ROWS
) -> pd.DataFrame:
    """Downsample df to target_rows using uniform stride sampling.

    Full implementation in Story 4.2 (auto-downsampling recovery path).
    """
    # TODO: implement in Story 4.2
    return df
