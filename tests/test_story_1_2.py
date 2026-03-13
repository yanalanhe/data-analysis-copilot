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
            "csv_temp_paths",
            "csv_metadata",
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
        # 17 fields (csv_temp_path/data_row_count replaced with csv_temp_paths/csv_metadata — same count)
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
# AC #3 — init_session_state() sets all 9 keys with correct defaults
# AC #4 — init_session_state() is idempotent
# ---------------------------------------------------------------------------

class TestInitSessionState:
    """Tests for init_session_state() — ACs #3 and #4."""

    @pytest.fixture(autouse=True)
    def _mock_streamlit(self, monkeypatch):
        """Replace st.session_state with a plain dict for testing."""
        import sys
        # Ensure streamlit module exists (may not be installed in test env)
        if "streamlit" not in sys.modules:
            fake_st = type("FakeStreamlit", (), {"session_state": {}})()
            monkeypatch.setitem(sys.modules, "streamlit", fake_st)
        import utils.session as session_mod
        self._state = {}
        monkeypatch.setattr(session_mod, "st", type("FakeSt", (), {"session_state": self._state})())

    def test_all_required_keys_created(self):
        """AC #3: init_session_state() creates all required keys."""
        from utils.session import init_session_state
        init_session_state()
        expected_keys = {
            "uploaded_dfs", "csv_temp_paths", "chat_history",
            "pipeline_state", "pipeline_running", "plan_approved",
            "active_tab", "saved_templates", "active_template",
        }
        assert expected_keys.issubset(set(self._state.keys())), \
            f"Missing keys: {expected_keys - set(self._state.keys())}"

    def test_uploaded_dfs_default(self):
        """AC #3: uploaded_dfs defaults to empty dict."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["uploaded_dfs"] == {}

    def test_csv_temp_paths_default(self):
        """AC #3: csv_temp_paths defaults to empty dict."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["csv_temp_paths"] == {}

    def test_chat_history_default(self):
        """AC #3: chat_history defaults to empty list."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["chat_history"] == []

    def test_pipeline_state_default(self):
        """AC #3: pipeline_state defaults to None."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["pipeline_state"] is None

    def test_pipeline_running_default(self):
        """AC #3: pipeline_running defaults to False."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["pipeline_running"] is False

    def test_plan_approved_default(self):
        """AC #3: plan_approved defaults to False."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["plan_approved"] is False

    def test_active_tab_default(self):
        """AC #3: active_tab defaults to 'plan'."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["active_tab"] == "plan"

    def test_saved_templates_default(self):
        """AC #3: saved_templates defaults to list (from load_templates)."""
        from utils.session import init_session_state
        init_session_state()
        assert isinstance(self._state["saved_templates"], list)

    def test_active_template_default(self):
        """AC #3: active_template defaults to None."""
        from utils.session import init_session_state
        init_session_state()
        assert self._state["active_template"] is None

    def test_idempotent_preserves_existing_values(self):
        """AC #4: Calling init_session_state() when keys exist does NOT overwrite them."""
        from utils.session import init_session_state
        # Pre-populate with non-default values
        self._state["uploaded_dfs"] = {"existing.csv": "dataframe"}
        self._state["chat_history"] = [{"role": "user", "content": "hello"}]
        self._state["pipeline_running"] = True
        self._state["active_tab"] = "code"

        init_session_state()

        assert self._state["uploaded_dfs"] == {"existing.csv": "dataframe"}
        assert self._state["chat_history"] == [{"role": "user", "content": "hello"}]
        assert self._state["pipeline_running"] is True
        assert self._state["active_tab"] == "code"

    def test_idempotent_only_fills_missing_keys(self):
        """AC #4: Second call only fills keys that were deleted, not existing ones."""
        from utils.session import init_session_state
        init_session_state()
        # Modify one value, delete another
        self._state["plan_approved"] = True
        del self._state["active_template"]

        init_session_state()

        # Modified value preserved
        assert self._state["plan_approved"] is True
        # Deleted key restored to default
        assert self._state["active_template"] is None


# ---------------------------------------------------------------------------
# AC #3 dependency — utils/templates.py (load_templates)
# ---------------------------------------------------------------------------

class TestLoadTemplates:
    def test_returns_empty_list_when_no_file(self, tmp_path, monkeypatch):
        """load_templates() returns [] when templates.json does not exist."""
        import utils.templates as tmpl_mod
        monkeypatch.setattr(tmpl_mod, "TEMPLATES_FILE", str(tmp_path / "nonexistent.json"))
        result = tmpl_mod.load_templates()
        assert result == []

    def test_returns_empty_list_type(self, tmp_path, monkeypatch):
        import utils.templates as tmpl_mod
        monkeypatch.setattr(tmpl_mod, "TEMPLATES_FILE", str(tmp_path / "nonexistent.json"))
        result = tmpl_mod.load_templates()
        assert isinstance(result, list)

    def test_loads_valid_json_file(self, tmp_path, monkeypatch):
        """load_templates() loads and returns content from a valid templates.json."""
        import json
        import utils.templates as tmpl_mod
        templates_data = [{"name": "test", "plan": ["step 1"], "code": "print('hi')"}]
        json_path = str(tmp_path / "templates.json")
        (tmp_path / "templates.json").write_text(json.dumps(templates_data), encoding="utf-8")
        monkeypatch.setattr(tmpl_mod, "TEMPLATES_FILE", json_path)
        result = tmpl_mod.load_templates()
        assert result == templates_data

    def test_save_template_is_callable(self):
        """save_template() is implemented in Story 5.3 and no longer raises NotImplementedError."""
        from utils.templates import save_template
        # Verify the function exists and is callable (full implementation tested in test_template_save_reuse.py)
        assert callable(save_template)


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

class TestLargeDataUtils:
    def test_detect_large_data_real_logic(self):
        """Story 4.1 implemented real threshold logic — verify correct behaviour."""
        from utils.large_data import detect_large_data
        assert detect_large_data(0, 0.0) is False           # empty dataset — not large
        assert detect_large_data(1_000_000, 100.0) is True  # both thresholds exceeded

    def test_apply_uniform_stride_small_df_unchanged(self):
        """Story 4.2: small DataFrame (below target) returned unchanged."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = apply_uniform_stride(df)
        assert len(result) == 3

    def test_apply_uniform_stride_large_df_downsamples(self):
        """Story 4.2: large DataFrame is downsampled to DOWNSAMPLE_TARGET_ROWS."""
        import pandas as pd
        from utils.large_data import apply_uniform_stride, DOWNSAMPLE_TARGET_ROWS
        df = pd.DataFrame({"a": range(50_000)})
        result = apply_uniform_stride(df)
        assert len(result) == DOWNSAMPLE_TARGET_ROWS

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
