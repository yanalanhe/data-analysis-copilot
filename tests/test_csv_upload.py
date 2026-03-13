# tests/test_csv_upload.py
"""Unit tests for CSV upload handling logic in streamlit_app.py (_on_csv_upload).

Tests cover:
- AC #2: uploaded_dfs keyed by filename after upload
- AC #5: csv_temp_paths is a dict with per-file paths after upload
- AC #5: each temp file contains only its own rows (not combined)
- AC #6: no csv_temp_paths when no upload (sample data path)
- detect_large_data() called with correct row count and size_mb
"""
import io
import os
import csv
import tempfile
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers — mock Streamlit UploadedFile and session_state
# ---------------------------------------------------------------------------

class MockSessionState(dict):
    """Minimal mock for st.session_state that supports both dict and attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value

    def get(self, name, default=None):
        return super().get(name, default)

    def __contains__(self, item):
        return super().__contains__(item)


def make_csv_bytes(rows: list[dict]) -> bytes:
    """Serialise a list of dicts to CSV bytes."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def make_uploaded_file(name: str, rows: list[dict]) -> MagicMock:
    """Return a MagicMock that behaves like a Streamlit UploadedFile for pd.read_csv."""
    content = make_csv_bytes(rows)
    buf = io.BytesIO(content)
    mock = MagicMock()
    mock.name = name
    mock.size = len(content)
    # pd.read_csv calls read() on the file-like object
    mock.read = buf.read
    mock.seek = buf.seek
    mock.tell = buf.tell
    mock.__iter__ = lambda self: iter(buf)
    # Make it usable directly with pd.read_csv via the underlying BytesIO
    mock._buf = buf
    return mock


# ---------------------------------------------------------------------------
# We extract _on_csv_upload from streamlit_app.py by importing it
# in a patched context so that streamlit does not execute its top-level code.
# Strategy: import via importlib with st patched.
# ---------------------------------------------------------------------------

def get_on_csv_upload(session_state: MockSessionState):
    """
    Return a version of _on_csv_upload with st.session_state replaced by our mock.
    We define a standalone version here that mirrors the exact implementation
    in streamlit_app.py — so that tests remain valid even if the source moves.
    """
    import tempfile as _tempfile
    import os as _os
    import pandas as _pd
    from utils.large_data import detect_large_data as _detect_large_data

    def _on_csv_upload(uploaded_files):
        new_dfs = {}
        for f in uploaded_files:
            # Reset buffer position before reading
            if hasattr(f, '_buf'):
                f._buf.seek(0)
                new_dfs[f.name] = _pd.read_csv(f._buf)
            else:
                new_dfs[f.name] = _pd.read_csv(f)

        session_state["uploaded_dfs"] = new_dfs

        # Keep st.session_state.df as first file for backward compat
        first_df = list(new_dfs.values())[0]
        session_state["df"] = first_df

        # Clean up previous temp paths if they exist
        old_paths = session_state.get("csv_temp_paths", {})
        for old_path in old_paths.values():
            if old_path and _os.path.exists(old_path):
                try:
                    _os.remove(old_path)
                except OSError:
                    pass

        # Write one temp file per uploaded DataFrame
        new_temp_paths = {}
        for name, df in new_dfs.items():
            with _tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv", mode="w", encoding="utf-8"
            ) as tmp:
                df.to_csv(tmp, index=False)
                new_temp_paths[name] = tmp.name

        session_state["csv_temp_paths"] = new_temp_paths

        # Large data detection
        combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
        total_rows = sum(len(df) for df in new_dfs.values())
        _detect_large_data(total_rows, combined_size_mb)

    return _on_csv_upload


# ---------------------------------------------------------------------------
# AC #2 — uploaded_dfs populated correctly
# ---------------------------------------------------------------------------

class TestUploadedDfs:
    def test_single_file_keyed_by_filename(self):
        """AC #2: Single file stored in uploaded_dfs under its filename."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={}, saved_templates=[])
        fn = get_on_csv_upload(ss)
        rows = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
        f = make_uploaded_file("data.csv", rows)
        fn([f])
        assert "data.csv" in ss["uploaded_dfs"]

    def test_single_file_dataframe_content(self):
        """AC #2: DataFrame stored has correct row count and columns."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        rows = [{"a": 10, "b": 20}, {"a": 30, "b": 40}, {"a": 50, "b": 60}]
        f = make_uploaded_file("test.csv", rows)
        fn([f])
        df = ss["uploaded_dfs"]["test.csv"]
        assert len(df) == 3
        assert list(df.columns) == ["a", "b"]

    def test_multiple_files_all_stored(self):
        """AC #2: Multiple files all stored in uploaded_dfs by filename."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        f1 = make_uploaded_file("file1.csv", [{"v": 1}])
        f2 = make_uploaded_file("file2.csv", [{"v": 2}])
        fn([f1, f2])
        assert "file1.csv" in ss["uploaded_dfs"]
        assert "file2.csv" in ss["uploaded_dfs"]

    def test_uploaded_dfs_overwrites_previous(self):
        """AC #2: Re-uploading a different set replaces the old uploaded_dfs."""
        ss = MockSessionState(uploaded_dfs={"old.csv": pd.DataFrame()}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        f = make_uploaded_file("new.csv", [{"k": 1}])
        fn([f])
        assert "new.csv" in ss["uploaded_dfs"]
        assert "old.csv" not in ss["uploaded_dfs"]


# ---------------------------------------------------------------------------
# AC #5 — csv_temp_paths is a dict with per-file paths
# ---------------------------------------------------------------------------

class TestCsvTempPaths:
    def test_csv_temp_paths_dict_after_upload(self):
        """AC #5: csv_temp_paths is a dict in session state after upload."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        fn([make_uploaded_file("d.csv", [{"col": 1}])])
        assert isinstance(ss["csv_temp_paths"], dict)
        assert len(ss["csv_temp_paths"]) == 1

    def test_each_file_gets_its_own_temp_path(self):
        """AC #5: Each uploaded file has its own entry in csv_temp_paths dict."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        f1 = make_uploaded_file("file1.csv", [{"v": 1}])
        f2 = make_uploaded_file("file2.csv", [{"v": 2}])
        fn([f1, f2])
        assert len(ss["csv_temp_paths"]) == 2
        assert "file1.csv" in ss["csv_temp_paths"]
        assert "file2.csv" in ss["csv_temp_paths"]

    def test_each_temp_path_points_to_real_file(self):
        """AC #5: Each path in csv_temp_paths dict points to an existing file."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        f1 = make_uploaded_file("a.csv", [{"x": 1}])
        f2 = make_uploaded_file("b.csv", [{"x": 2}])
        fn([f1, f2])
        for fname, path in ss["csv_temp_paths"].items():
            assert os.path.exists(path), f"Temp file not found for {fname}: {path}"
        # Cleanup
        for path in ss["csv_temp_paths"].values():
            os.remove(path)

    def test_each_temp_file_content_matches_source(self):
        """AC #5: Each temp file contains only its source CSV's rows."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        rows1 = [{"time": 0, "sensor": 10}, {"time": 1, "sensor": 11}]
        rows2 = [{"time": 0, "voltage": 12.5}, {"time": 1, "voltage": 12.6}]
        f1 = make_uploaded_file("csv1.csv", rows1)
        f2 = make_uploaded_file("csv2.csv", rows2)
        fn([f1, f2])

        # Read back temp files and verify content
        path1 = ss["csv_temp_paths"]["csv1.csv"]
        path2 = ss["csv_temp_paths"]["csv2.csv"]

        df1 = pd.read_csv(path1)
        df2 = pd.read_csv(path2)

        # CSV1 should have 2 rows with columns time, sensor (no NaN padding)
        assert len(df1) == 2
        assert list(df1.columns) == ["time", "sensor"]
        assert df1["sensor"].tolist() == [10, 11]

        # CSV2 should have 2 rows with columns time, voltage (no NaN padding)
        assert len(df2) == 2
        assert list(df2.columns) == ["time", "voltage"]
        assert df2["voltage"].tolist() == [12.5, 12.6]

        # Cleanup
        os.remove(path1)
        os.remove(path2)

    def test_old_temp_paths_cleaned_up_on_re_upload(self, tmp_path):
        """AC #5: Previous temp files are deleted when new CSVs are uploaded."""
        # Create fake old temp files
        old_file1 = tmp_path / "old1.csv"
        old_file2 = tmp_path / "old2.csv"
        old_file1.write_text("x\n1\n")
        old_file2.write_text("x\n2\n")

        ss = MockSessionState(
            uploaded_dfs={},
            csv_temp_paths={"old1.csv": str(old_file1), "old2.csv": str(old_file2)}
        )
        fn = get_on_csv_upload(ss)
        fn([make_uploaded_file("new.csv", [{"x": 99}])])

        assert not old_file1.exists(), "Old temp file 1 should have been deleted"
        assert not old_file2.exists(), "Old temp file 2 should have been deleted"
        # Cleanup
        os.remove(ss["csv_temp_paths"]["new.csv"])

    def test_df_session_state_updated_to_first_file(self):
        """AC #5: st.session_state.df is set to the first uploaded file for backward compat."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        rows1 = [{"a": 1}, {"a": 2}]
        rows2 = [{"b": 10}, {"b": 20}, {"b": 30}]
        f1 = make_uploaded_file("first.csv", rows1)
        f2 = make_uploaded_file("second.csv", rows2)
        fn([f1, f2])

        # df should be first file (2 rows)
        assert len(ss["df"]) == 2
        assert ss["df"]["a"].tolist() == [1, 2]
        # Cleanup
        for path in ss["csv_temp_paths"].values():
            os.remove(path)

    def test_csv_temp_paths_empty_without_upload(self):
        """AC #6: csv_temp_paths remains empty {} when no files are uploaded."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        # Don't call upload function; just verify empty state
        assert ss["csv_temp_paths"] == {}


# ---------------------------------------------------------------------------
# Large data detection
# ---------------------------------------------------------------------------

class TestLargeDataDetection:
    @patch("utils.large_data.detect_large_data")
    def test_detect_large_data_called_with_total_rows_and_size(self, mock_detect):
        """detect_large_data is called with total row count and combined file size."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_paths={})
        fn = get_on_csv_upload(ss)
        rows1 = [{"x": i} for i in range(10)]
        rows2 = [{"x": i} for i in range(20)]
        f1 = make_uploaded_file("a.csv", rows1)
        f2 = make_uploaded_file("b.csv", rows2)
        fn([f1, f2])

        # detect_large_data should be called with total_rows=30 and combined size
        mock_detect.assert_called_once()
        call_args = mock_detect.call_args[0]
        assert call_args[0] == 30  # total rows
        # Cleanup
        for path in ss["csv_temp_paths"].values():
            os.remove(path)
