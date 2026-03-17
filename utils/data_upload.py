"""CSV upload and data-preparation helpers.

Handles multi-file upload, temp-file management, large-data detection,
and uniform-stride downsampling.  Pure data-layer logic — no LLM calls.
"""

import os
import tempfile

import streamlit as st
import pandas as pd

from utils.error_translation import translate_error


def _combine_uploaded_dfs(uploaded_dfs: dict) -> pd.DataFrame:
    """Combine uploaded DataFrames into a single DataFrame.

    Single-file: returns the DataFrame directly.
    Multi-file: concatenates with ignore_index=True.
    """
    if len(uploaded_dfs) == 1:
        return list(uploaded_dfs.values())[0]
    return pd.concat(list(uploaded_dfs.values()), ignore_index=True)


def on_csv_upload(uploaded_files) -> None:
    """Handle CSV file upload: populate uploaded_dfs, write per-file temp files, update df.

    Stores each file as a DataFrame in st.session_state["uploaded_dfs"] keyed by filename.
    Writes one temp CSV per file and sets st.session_state["csv_temp_paths"] as a dict.
    Updates st.session_state.df to first file for backward compat with run_tests() and existing pipeline.
    Calls detect_large_data() and stores result in session state (Story 4.1).
    Skips re-processing if the uploaded file set has not changed since last call.
    """
    from utils.large_data import detect_large_data

    # Skip re-processing if the same files are still in the uploader (rerun guard)
    upload_signature = tuple(sorted((f.name, f.size) for f in uploaded_files))
    if st.session_state.get("_upload_signature") == upload_signature:
        return
    st.session_state["_upload_signature"] = upload_signature

    # Story 4.2: Reset recovery state when new files are uploaded
    st.session_state["recovery_applied"] = ""

    # Load each uploaded file into a DataFrame
    new_dfs = {}
    for f in uploaded_files:
        try:
            new_dfs[f.name] = pd.read_csv(f)
        except Exception as e:
            st.error(f"Failed to read **{f.name}**: {translate_error(e)}")
            continue

    if not new_dfs:
        return

    st.session_state["uploaded_dfs"] = new_dfs

    # Keep st.session_state.df as first file for backward compat
    first_df = list(new_dfs.values())[0]
    st.session_state.df = first_df

    # Clean up previous temp paths if they exist
    old_paths = st.session_state.get("csv_temp_paths", {})
    for old_path in old_paths.values():
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass  # Safe to ignore — temp file may already be gone

    # Write one temp file per uploaded DataFrame
    new_temp_paths = {}
    for name, df in new_dfs.items():
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", encoding="utf-8"
        ) as tmp:
            df.to_csv(tmp, index=False)
            new_temp_paths[name] = tmp.name

    st.session_state["csv_temp_paths"] = new_temp_paths

    # Large data detection — runs on upload before any pipeline execution (NFR5, Story 4.1)
    combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
    total_rows = sum(len(df) for df in new_dfs.values())
    is_large = detect_large_data(total_rows, combined_size_mb)
    if is_large:
        st.session_state["large_data_detected"] = True
        file_count = len(new_dfs)
        st.session_state["large_data_message"] = (
            f"Your dataset has {total_rows:,} rows across {file_count} files / {combined_size_mb:.1f} MB, "
            "which exceeds the visualization threshold."
        )
    else:
        st.session_state["large_data_detected"] = False
        st.session_state["large_data_message"] = ""


def apply_downsample() -> None:
    """Apply uniform stride downsampling to each uploaded file independently.

    Overwrites each temp CSV with its downsampled data.
    Sets recovery_applied = "downsampled" in session state.
    Called from the auto-downsample button in _execution_panel().
    """
    from utils.large_data import apply_uniform_stride

    uploaded_dfs = st.session_state.get("uploaded_dfs", {})
    csv_temp_paths = st.session_state.get("csv_temp_paths", {})
    if not uploaded_dfs:
        st.warning("No uploaded dataset found. Please upload a CSV file first.")
        return

    # Downsample each file independently and overwrite its temp file
    new_temp_paths = {}
    for name, df in uploaded_dfs.items():
        downsampled_df = apply_uniform_stride(df)

        if name in csv_temp_paths and csv_temp_paths[name]:
            temp_path = csv_temp_paths[name]
            if os.path.exists(temp_path):
                downsampled_df.to_csv(temp_path, index=False)
                new_temp_paths[name] = temp_path
            else:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv", mode="w", encoding="utf-8"
                ) as tmp:
                    downsampled_df.to_csv(tmp, index=False)
                    new_temp_paths[name] = tmp.name
        else:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv", mode="w", encoding="utf-8"
            ) as tmp:
                downsampled_df.to_csv(tmp, index=False)
                new_temp_paths[name] = tmp.name

    st.session_state["csv_temp_paths"] = new_temp_paths

    # Update df in session to first downsampled file for backward compat with existing pipeline
    first_name = list(uploaded_dfs.keys())[0]
    st.session_state.df = apply_uniform_stride(uploaded_dfs[first_name])
    st.session_state["recovery_applied"] = "downsampled"
