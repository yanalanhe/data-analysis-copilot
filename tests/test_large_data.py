# tests/test_large_data.py
"""Unit tests for large dataset threshold detection and uniform stride downsampling.

Stories 4.1 (detect_large_data) and 4.2 (apply_uniform_stride).
"""
import ast
import pathlib

from utils.large_data import (
    DOWNSAMPLE_TARGET_ROWS,
    LARGE_DATA_ROW_THRESHOLD,
    LARGE_DATA_SIZE_THRESHOLD_MB,
    detect_large_data,
)


class TestConstants:
    """Test that threshold constants have the correct values."""

    def test_large_data_row_threshold_value(self):
        assert LARGE_DATA_ROW_THRESHOLD == 100_000

    def test_large_data_size_threshold_mb_value(self):
        assert LARGE_DATA_SIZE_THRESHOLD_MB == 20.0

    def test_downsample_target_rows_value(self):
        assert DOWNSAMPLE_TARGET_ROWS == 10_000


class TestDetectLargeDataRowThreshold:
    """Tests for the row count threshold (>= 100,000 rows)."""

    def test_exactly_at_row_threshold_returns_true(self):
        # >= not >, so exactly 100_000 must return True
        assert detect_large_data(100_000, 5.0) is True

    def test_one_below_row_threshold_returns_false(self):
        assert detect_large_data(99_999, 5.0) is False

    def test_above_row_threshold_returns_true(self):
        assert detect_large_data(100_001, 0.1) is True

    def test_well_above_row_threshold_returns_true(self):
        assert detect_large_data(200_000, 5.0) is True


class TestDetectLargeDataSizeThreshold:
    """Tests for the file size threshold (>= 20 MB)."""

    def test_exactly_at_size_threshold_returns_true(self):
        # >= not >, so exactly 20.0 MB must return True
        assert detect_large_data(1, 20.0) is True

    def test_one_tenth_below_size_threshold_returns_false(self):
        assert detect_large_data(50_000, 19.9) is False

    def test_above_size_threshold_returns_true(self):
        assert detect_large_data(50_000, 20.0) is True

    def test_well_above_size_threshold_returns_true(self):
        assert detect_large_data(1, 50.0) is True


class TestDetectLargeDataBothThresholds:
    """Tests for OR logic — either threshold triggers the result."""

    def test_both_thresholds_exceeded_returns_true(self):
        assert detect_large_data(200_000, 50.0) is True

    def test_both_below_thresholds_returns_false(self):
        assert detect_large_data(50_000, 5.0) is False

    def test_empty_dataset_returns_false(self):
        assert detect_large_data(0, 0.0) is False

    def test_only_row_threshold_exceeded_returns_true(self):
        assert detect_large_data(150_000, 0.1) is True

    def test_only_size_threshold_exceeded_returns_true(self):
        assert detect_large_data(1, 25.0) is True


class TestApplyUniformStride:
    """Tests for apply_uniform_stride() — uniform stride downsampling."""

    def test_large_df_downsamples_to_target_rows(self):
        """DataFrame with 100,000 rows → exactly DOWNSAMPLE_TARGET_ROWS (10,000) rows."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(100_000)})
        result = apply_uniform_stride(df)
        assert len(result) == DOWNSAMPLE_TARGET_ROWS

    def test_50k_rows_downsamples_to_target(self):
        """DataFrame with 50,000 rows → exactly 10,000 rows."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(50_000)})
        result = apply_uniform_stride(df)
        assert len(result) == DOWNSAMPLE_TARGET_ROWS

    def test_below_target_returns_unchanged(self):
        """DataFrame with 9,999 rows → returned unchanged (no downsampling)."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(9_999)})
        result = apply_uniform_stride(df)
        assert len(result) == 9_999

    def test_exactly_at_target_returns_unchanged(self):
        """DataFrame with 10,000 rows → returned unchanged (at target, not above)."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(10_000)})
        result = apply_uniform_stride(df)
        assert len(result) == 10_000

    def test_just_above_target_downsamples(self):
        """DataFrame with 10,001 rows → exactly 10,000 rows."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(10_001)})
        result = apply_uniform_stride(df)
        assert len(result) == 10_000

    def test_preserves_column_names(self):
        """Output columns match input columns."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"col_a": range(50_000), "col_b": range(50_000)})
        result = apply_uniform_stride(df)
        assert list(result.columns) == ["col_a", "col_b"]

    def test_index_is_reset(self):
        """Result index starts at 0 and is contiguous (reset_index applied)."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(50_000)})
        result = apply_uniform_stride(df)
        assert list(result.index) == list(range(len(result)))

    def test_uniform_coverage_not_just_first_rows(self):
        """Stride sampling covers entire dataset — result is NOT just the first N rows."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(50_000)})
        result = apply_uniform_stride(df)
        # If it were just .head(10_000), the max value would be 9999
        # Uniform stride means the last value should be near 49999
        assert result["value"].max() > 40_000

    def test_custom_target_rows(self):
        """apply_uniform_stride respects custom target_rows parameter."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": range(20)})
        result = apply_uniform_stride(df, target_rows=5)
        assert len(result) == 5

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame returns empty DataFrame without error."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": []})
        result = apply_uniform_stride(df)
        assert len(result) == 0

    def test_single_row_returns_unchanged(self):
        """Single-row DataFrame returns that row unchanged."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"value": [42]})
        result = apply_uniform_stride(df)
        assert len(result) == 1
        assert result["value"].iloc[0] == 42


class TestLargeDataModuleBoundary:
    """Test that utils/large_data.py does not import streamlit."""

    def test_large_data_does_not_import_streamlit(self):
        source = pathlib.Path("utils/large_data.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "streamlit" not in (alias.name or ""), (
                        f"streamlit imported in large_data.py: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert "streamlit" not in (node.module or ""), (
                    f"streamlit imported in large_data.py: {node.module}"
                )
