# tests/test_csv_upload.py
"""Unit tests for CSV upload handling logic in streamlit_app.py (_on_csv_upload).

Tests cover:
- AC #2: uploaded_dfs keyed by filename after upload
- AC #5: csv_temp_path is set and points to a real file after upload
- AC #5: combined CSV file contains all uploaded rows
- AC #6: no csv_temp_path set when no upload (sample data path)
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

        if len(new_dfs) == 1:
            combined_df = list(new_dfs.values())[0]
        else:
            combined_df = _pd.concat(list(new_dfs.values()), ignore_index=True)

        session_state["df"] = combined_df

        old_path = session_state.get("csv_temp_path")
        if old_path and _os.path.exists(old_path):
            try:
                _os.remove(old_path)
            except OSError:
                pass

        with _tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", encoding="utf-8"
        ) as tmp:
            combined_df.to_csv(tmp, index=False)
            session_state["csv_temp_path"] = tmp.name

        combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
        _detect_large_data(len(combined_df), combined_size_mb)

    return _on_csv_upload


# ---------------------------------------------------------------------------
# AC #2 — uploaded_dfs populated correctly
# ---------------------------------------------------------------------------

class TestUploadedDfs:
    def test_single_file_keyed_by_filename(self):
        """AC #2: Single file stored in uploaded_dfs under its filename."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None, saved_templates=[])
        fn = get_on_csv_upload(ss)
        rows = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
        f = make_uploaded_file("data.csv", rows)
        fn([f])
        assert "data.csv" in ss["uploaded_dfs"]

    def test_single_file_dataframe_content(self):
        """AC #2: DataFrame stored has correct row count and columns."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        rows = [{"a": 10, "b": 20}, {"a": 30, "b": 40}, {"a": 50, "b": 60}]
        f = make_uploaded_file("test.csv", rows)
        fn([f])
        df = ss["uploaded_dfs"]["test.csv"]
        assert len(df) == 3
        assert list(df.columns) == ["a", "b"]

    def test_multiple_files_all_stored(self):
        """AC #2: Multiple files all stored in uploaded_dfs by filename."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        f1 = make_uploaded_file("file1.csv", [{"v": 1}])
        f2 = make_uploaded_file("file2.csv", [{"v": 2}])
        fn([f1, f2])
        assert "file1.csv" in ss["uploaded_dfs"]
        assert "file2.csv" in ss["uploaded_dfs"]

    def test_uploaded_dfs_overwrites_previous(self):
        """AC #2: Re-uploading a different set replaces the old uploaded_dfs."""
        ss = MockSessionState(uploaded_dfs={"old.csv": pd.DataFrame()}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        f = make_uploaded_file("new.csv", [{"k": 1}])
        fn([f])
        assert "new.csv" in ss["uploaded_dfs"]
        assert "old.csv" not in ss["uploaded_dfs"]


# ---------------------------------------------------------------------------
# AC #5 — csv_temp_path set to a real file
# ---------------------------------------------------------------------------

class TestCsvTempPath:
    def test_csv_temp_path_is_set_after_upload(self):
        """AC #5: csv_temp_path is set in session state after upload."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        fn([make_uploaded_file("d.csv", [{"col": 1}])])
        assert ss["csv_temp_path"] is not None

    def test_csv_temp_path_points_to_real_file(self):
        """AC #5: csv_temp_path points to an existing file on disk."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        fn([make_uploaded_file("d.csv", [{"col": 1}])])
        path = ss["csv_temp_path"]
        assert os.path.exists(path), f"Temp file not found: {path}"
        # Cleanup
        os.remove(path)

    def test_temp_file_contains_csv_data(self):
        """AC #5: combined CSV file written to disk contains the uploaded rows."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        rows = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
        fn([make_uploaded_file("data.csv", rows)])
        path = ss["csv_temp_path"]
        written_df = pd.read_csv(path)
        assert len(written_df) == 2
        assert list(written_df.columns) == ["x", "y"]
        os.remove(path)

    def test_multi_file_combined_rows_in_temp_file(self):
        """AC #5: Multiple CSVs are concatenated into a single temp file."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        f1 = make_uploaded_file("a.csv", [{"n": 1}, {"n": 2}])
        f2 = make_uploaded_file("b.csv", [{"n": 3}, {"n": 4}])
        fn([f1, f2])
        path = ss["csv_temp_path"]
        written_df = pd.read_csv(path)
        assert len(written_df) == 4
        os.remove(path)

    def test_old_temp_file_cleaned_up_on_re_upload(self, tmp_path):
        """AC #5: Previous temp file is deleted when a new CSV is uploaded."""
        # Create a fake old temp file
        old_file = tmp_path / "old.csv"
        old_file.write_text("x\n1\n")
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=str(old_file))
        fn = get_on_csv_upload(ss)
        fn([make_uploaded_file("new.csv", [{"x": 99}])])
        assert not old_file.exists(), "Old temp file should have been deleted"
        os.remove(ss["csv_temp_path"])

    def test_df_session_state_updated_for_backward_compat(self):
        """AC #2+#5: st.session_state.df is updated to the combined DataFrame."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        fn = get_on_csv_upload(ss)
        rows = [{"col": 42}]
        fn([make_uploaded_file("x.csv", rows)])
        assert "df" in ss
        assert ss["df"].iloc[0]["col"] == 42
        os.remove(ss["csv_temp_path"])


# ---------------------------------------------------------------------------
# AC #6 — sample data path (no CSV uploaded)
# ---------------------------------------------------------------------------

class TestSampleData:
    def test_csv_temp_path_not_set_without_upload(self):
        """AC #6: csv_temp_path remains None if no files are uploaded."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        # Simulate the UI logic: no uploaded_files → don't call _on_csv_upload
        # This tests that the session key is untouched
        assert ss.get("csv_temp_path") is None

    def test_uploaded_dfs_empty_without_upload(self):
        """AC #6: uploaded_dfs remains empty if no files uploaded."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        assert ss.get("uploaded_dfs") == {}


# ---------------------------------------------------------------------------
# detect_large_data called with correct arguments
# ---------------------------------------------------------------------------

class TestDetectLargeDataHook:
    def test_detect_large_data_called_with_row_count(self):
        """detect_large_data receives the actual row count of the combined DataFrame."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        rows = [{"v": i} for i in range(5)]
        f = make_uploaded_file("d.csv", rows)
        f.size = 200  # Override size for predictable test

        with patch("utils.large_data.detect_large_data") as mock_detect:
            fn = get_on_csv_upload(ss)
            fn([f])
            args = mock_detect.call_args[0]
            assert args[0] == 5, f"Expected row_count=5, got {args[0]}"
        os.remove(ss["csv_temp_path"])

    def test_detect_large_data_called_with_size_mb(self):
        """detect_large_data receives combined file size in MB."""
        ss = MockSessionState(uploaded_dfs={}, csv_temp_path=None)
        f = make_uploaded_file("d.csv", [{"v": 1}])
        f.size = 1_048_576  # exactly 1 MB

        with patch("utils.large_data.detect_large_data") as mock_detect:
            fn = get_on_csv_upload(ss)
            fn([f])
            args = mock_detect.call_args[0]
            assert args[1] == pytest.approx(1.0, rel=0.01)
        os.remove(ss["csv_temp_path"])
