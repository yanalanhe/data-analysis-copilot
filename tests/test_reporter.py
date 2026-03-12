"""Tests for pipeline/nodes/reporter.py — render_report() node.

Tests verify:
- render_report() is importable and callable
- render_report() returns a dict (empty — passthrough)
- render_report() does not mutate the input state
- reporter.py does not import streamlit (module boundary rule)
"""
import ast
import pathlib

import pytest

from pipeline.nodes.reporter import render_report
from pipeline.state import PipelineState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    """Build a minimal PipelineState-compatible dict for testing."""
    base: dict = {
        "user_query": "test query",
        "csv_temp_path": "",
        "data_row_count": 10,
        "intent": "report",
        "plan": ["Step 1", "Step 2"],
        "generated_code": "print('hello')",
        "validation_errors": [],
        "execution_output": "Output text",
        "execution_success": True,
        "retry_count": 0,
        "replan_triggered": False,
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
        "large_data_detected": False,
        "large_data_message": "",
        "recovery_applied": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Basic contract tests (AC: #4, #5)
# ---------------------------------------------------------------------------

class TestRenderReportBasicContract:

    def test_render_report_returns_dict(self):
        """render_report() returns a dict — empty passthrough."""
        result = render_report(_make_state())
        assert isinstance(result, dict)

    def test_render_report_returns_empty_dict_passthrough(self):
        """render_report() with populated charts/text returns {} — no state mutations."""
        state = _make_state(
            report_charts=[b"fakepng1", b"fakepng2"],
            report_text="Trend analysis: values increased over time.",
        )
        result = render_report(state)
        assert result == {}

    def test_render_report_empty_state_returns_empty_dict(self):
        """render_report() with empty charts/text still returns {} without raising."""
        state = _make_state(report_charts=[], report_text="")
        result = render_report(state)
        assert result == {}

    def test_render_report_with_only_charts(self):
        """render_report() returns {} when only charts are present."""
        state = _make_state(report_charts=[b"\x89PNG\r\n"], report_text="")
        result = render_report(state)
        assert result == {}

    def test_render_report_with_only_text(self):
        """render_report() returns {} when only report_text is present."""
        state = _make_state(report_charts=[], report_text="Summary: data looks good.")
        result = render_report(state)
        assert result == {}

    def test_render_report_does_not_raise(self):
        """render_report() never raises on any valid state."""
        state = _make_state()
        try:
            render_report(state)
        except Exception as exc:
            pytest.fail(f"render_report() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# State immutability tests
# ---------------------------------------------------------------------------

class TestRenderReportStateImmutability:

    def test_render_report_does_not_mutate_report_charts(self):
        """render_report() does not modify report_charts list."""
        charts = [b"fakepng"]
        state = _make_state(report_charts=charts)
        render_report(state)
        assert state["report_charts"] == [b"fakepng"]

    def test_render_report_does_not_mutate_report_text(self):
        """render_report() does not modify report_text string."""
        state = _make_state(report_text="Original analysis text.")
        render_report(state)
        assert state["report_text"] == "Original analysis text."

    def test_render_report_does_not_add_keys_to_input(self):
        """render_report() does not add keys to the input state dict."""
        state = _make_state()
        original_keys = set(state.keys())
        render_report(state)
        assert set(state.keys()) == original_keys

    def test_render_report_input_unchanged_after_call(self):
        """render_report() leaves the entire input state unchanged."""
        state = _make_state(
            report_charts=[b"chart1"],
            report_text="Analysis result",
            retry_count=2,
        )
        import copy
        state_copy = copy.deepcopy(state)
        render_report(state)
        assert state == state_copy


# ---------------------------------------------------------------------------
# Module boundary test — MUST NOT import streamlit
# ---------------------------------------------------------------------------

class TestReporterModuleBoundary:

    def test_reporter_does_not_import_streamlit(self):
        """reporter.py must never import streamlit (module boundary rule)."""
        source = pathlib.Path("pipeline/nodes/reporter.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "streamlit" not in (alias.name or ""), (
                        f"streamlit imported in reporter.py: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "streamlit" not in module, (
                    f"streamlit imported in reporter.py: {module}"
                )

    def test_reporter_importable_without_streamlit_context(self):
        """reporter.py imports cleanly without a Streamlit server running."""
        # If this test runs at all, the import succeeded (import happens at module load)
        from pipeline.nodes.reporter import render_report as _rf
        assert callable(_rf)
