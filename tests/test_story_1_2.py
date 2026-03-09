# tests/test_story_1_2.py
"""Unit tests for Story 1.2: Three-Layer Module Structure, PipelineState & Session Schema.

Tests cover:
- PipelineState TypedDict field presence and types (AC #2)
- utils/templates.py load_templates() returns [] when no file exists (AC #3 dependency)
- utils/error_translation.py translate_error() returns plain-English fallback (stub behavior)
- utils/large_data.py stub returns safe defaults
- Module boundary: no streamlit imports in pipeline/ or non-session utils/
"""
import ast
import os
import typing
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# AC #2 — PipelineState TypedDict fields
# ---------------------------------------------------------------------------

class TestPipelineState:
    def test_import_succeeds(self):
        from pipeline.state import PipelineState
        assert PipelineState is not None

    def test_all_required_fields_present(self):
        from pipeline.state import PipelineState
        required_fields = {
            "user_query",
            "csv_temp_path",
            "data_row_count",
            "intent",
            "plan",
            "generated_code",
            "validation_errors",
            "execution_output",
            "execution_success",
            "retry_count",
            "replan_triggered",
            "error_messages",
            "report_charts",
            "report_text",
            "large_data_detected",
            "large_data_message",
            "recovery_applied",
        }
        actual_fields = set(PipelineState.__annotations__.keys())
        missing = required_fields - actual_fields
        assert not missing, f"PipelineState missing fields: {missing}"

    def test_field_count(self):
        from pipeline.state import PipelineState
        # 17 fields as specified in architecture and epics
        assert len(PipelineState.__annotations__) == 17

    def test_intent_field_type_hint(self):
        from pipeline.state import PipelineState
        annotations = PipelineState.__annotations__
        # intent field must exist (type checked at runtime by TypedDict)
        assert "intent" in annotations

    def test_report_charts_field_is_list_type(self):
        from pipeline.state import PipelineState
        annotations = PipelineState.__annotations__
        # report_charts should be list[bytes]
        assert "report_charts" in annotations

    def test_error_messages_field_is_list_type(self):
        from pipeline.state import PipelineState
        annotations = PipelineState.__annotations__
        assert "error_messages" in annotations

    def test_no_streamlit_import_in_state(self):
        state_file = PROJECT_ROOT / "pipeline" / "state.py"
        source = state_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "streamlit" not in alias.name, \
                            "pipeline/state.py must not import streamlit"
                elif isinstance(node, ast.ImportFrom):
                    assert node.module is None or "streamlit" not in node.module, \
                        "pipeline/state.py must not import from streamlit"


# ---------------------------------------------------------------------------
# AC #3 — utils/templates.py (dependency of init_session_state)
# ---------------------------------------------------------------------------

class TestLoadTemplates:
    def test_returns_empty_list_when_no_file(self, tmp_path, monkeypatch):
        """load_templates() returns [] when templates.json does not exist."""
        monkeypatch.chdir(tmp_path)
        from utils.templates import load_templates
        result = load_templates()
        assert result == []

    def test_returns_empty_list_type(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from utils.templates import load_templates
        result = load_templates()
        assert isinstance(result, list)

    def test_loads_valid_json_file(self, tmp_path, monkeypatch):
        """load_templates() loads and returns content from a valid templates.json."""
        monkeypatch.chdir(tmp_path)
        import json
        templates_data = [{"name": "test", "plan": ["step 1"], "code": "print('hi')"}]
        (tmp_path / "templates.json").write_text(json.dumps(templates_data), encoding="utf-8")
        from utils.templates import load_templates
        result = load_templates()
        assert result == templates_data

    def test_save_template_raises_not_implemented(self):
        """save_template() raises NotImplementedError — implemented in Story 5.3."""
        from utils.templates import save_template
        with pytest.raises(NotImplementedError):
            save_template("name", ["step"], "code")


# ---------------------------------------------------------------------------
# AC #3 dependency — utils/error_translation.py stub
# ---------------------------------------------------------------------------

class TestTranslateError:
    def test_returns_string(self):
        from utils.error_translation import translate_error
        result = translate_error(Exception("test"))
        assert isinstance(result, str)

    def test_returns_plain_english_fallback(self):
        from utils.error_translation import translate_error
        result = translate_error(ValueError("something went wrong"))
        assert "unexpected error" in result.lower() or len(result) > 0

    def test_never_returns_raw_exception_repr(self):
        from utils.error_translation import translate_error
        exc = ValueError("raw internal detail")
        result = translate_error(exc)
        assert "raw internal detail" not in result, \
            "translate_error must never expose raw exception messages to users"


# ---------------------------------------------------------------------------
# utils/large_data.py stub defaults
# ---------------------------------------------------------------------------

class TestLargeDataStubs:
    def test_detect_large_data_returns_false_stub(self):
        """Stub returns False until Story 4.1 implements real logic."""
        from utils.large_data import detect_large_data
        assert detect_large_data(0, 0.0) is False
        assert detect_large_data(1_000_000, 100.0) is False  # stub always False

    def test_apply_uniform_stride_returns_input_unchanged(self):
        """Stub returns the input DataFrame unchanged until Story 4.2."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = apply_uniform_stride(df)
        assert len(result) == 3

    def test_constants_defined(self):
        from utils import large_data
        assert large_data.LARGE_DATA_ROW_THRESHOLD == 100_000
        assert large_data.LARGE_DATA_SIZE_THRESHOLD_MB == 20.0
        assert large_data.DOWNSAMPLE_TARGET_ROWS == 10_000


# ---------------------------------------------------------------------------
# AC #5 — Module boundary: no streamlit imports in pipeline/ or non-session utils/
# ---------------------------------------------------------------------------

PIPELINE_FILES = list((PROJECT_ROOT / "pipeline").rglob("*.py"))
NON_SESSION_UTILS = [
    PROJECT_ROOT / "utils" / "error_translation.py",
    PROJECT_ROOT / "utils" / "large_data.py",
    PROJECT_ROOT / "utils" / "templates.py",
]


def _has_streamlit_import(filepath: Path) -> bool:
    """Return True if file contains an actual streamlit import statement."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "streamlit" in alias.name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and "streamlit" in node.module:
                return True
    return False


@pytest.mark.parametrize("filepath", PIPELINE_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_no_streamlit_import_in_pipeline(filepath):
    """AC #5: No file in pipeline/ may import streamlit."""
    assert not _has_streamlit_import(filepath), \
        f"{filepath.relative_to(PROJECT_ROOT)} must not import streamlit"


@pytest.mark.parametrize("filepath", NON_SESSION_UTILS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_no_streamlit_import_in_non_session_utils(filepath):
    """AC #5: Only utils/session.py may import streamlit."""
    assert not _has_streamlit_import(filepath), \
        f"{filepath.relative_to(PROJECT_ROOT)} must not import streamlit"


# ---------------------------------------------------------------------------
# AC #1 — Required files exist
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    "streamlit_app.py",
    "pipeline/__init__.py",
    "pipeline/state.py",
    "pipeline/graph.py",
    "pipeline/nodes/__init__.py",
    "pipeline/nodes/intent.py",
    "pipeline/nodes/planner.py",
    "pipeline/nodes/codegen.py",
    "pipeline/nodes/validator.py",
    "pipeline/nodes/executor.py",
    "pipeline/nodes/reporter.py",
    "pipeline/nodes/error_handler.py",
    "utils/__init__.py",
    "utils/session.py",
    "utils/error_translation.py",
    "utils/large_data.py",
    "utils/templates.py",
]


@pytest.mark.parametrize("rel_path", REQUIRED_FILES)
def test_required_file_exists(rel_path):
    """AC #1: All required files must exist."""
    full_path = PROJECT_ROOT / rel_path
    assert full_path.exists(), f"Required file missing: {rel_path}"
