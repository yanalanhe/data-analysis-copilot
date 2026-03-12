# tests/test_graph.py
"""Tests for pipeline/graph.py and pipeline/nodes/error_handler.py.

Tests LangGraph graph structure, route_after_execution routing logic,
handle_error node behavior, and module boundary guards.

Covers Story 3.5 ACs #1–6.

IMPORTANT: No real LLM API calls are made in this test file.
  - route_after_execution and handle_error are pure functions tested directly.
  - Graph structure is verified by inspecting compiled_graph.nodes.
  - Module boundary is verified via ast.parse on source files.
"""
import ast
import pathlib

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales over time",
        "csv_temp_path": None,
        "data_row_count": 100,
        "intent": "report",
        "plan": ["Load data", "Plot chart"],
        "generated_code": "",
        "validation_errors": [],
        "execution_output": "",
        "execution_success": False,
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
# AC #2: route_after_execution routing logic (pure function, no API calls)
# ---------------------------------------------------------------------------

class TestRouteAfterExecution:
    """Tests for the route_after_execution routing function."""

    def test_routes_to_render_report_on_success(self):
        """AC #2: execution_success=True → returns 'render_report'."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=True, retry_count=0)
        assert route_after_execution(state) == "render_report"

    def test_routes_to_generate_code_on_first_failure(self):
        """AC #3: execution_success=False, retry_count=1 (after first increment) → 'generate_code'."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=1)
        assert route_after_execution(state) == "generate_code"

    def test_routes_to_generate_code_on_second_failure(self):
        """AC #3: execution_success=False, retry_count=2 → 'generate_code'."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=2)
        assert route_after_execution(state) == "generate_code"

    def test_routes_to_generate_plan_at_max_retries(self):
        """AC #4: execution_success=False, retry_count=3 → 'generate_plan' (adaptive replan)."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=3)
        assert route_after_execution(state) == "generate_plan"

    def test_routes_to_generate_plan_at_retry_4(self):
        """AC #4: retry_count=4 → still returns 'generate_plan' (within replan window)."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=4)
        assert route_after_execution(state) == "generate_plan"

    def test_routes_to_render_report_at_max_replan(self):
        """Safety cap: retry_count >= 6 → returns 'render_report' to prevent infinite loop."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=6)
        assert route_after_execution(state) == "render_report"

    def test_routes_to_render_report_beyond_max_replan(self):
        """Safety cap: retry_count=10 → still returns 'render_report'."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=False, retry_count=10)
        assert route_after_execution(state) == "render_report"

    def test_route_returns_render_report_regardless_of_retry_count(self):
        """AC #2: success=True with high retry_count still routes to render_report."""
        from pipeline.graph import route_after_execution
        state = _make_state(execution_success=True, retry_count=3)
        assert route_after_execution(state) == "render_report"

    def test_route_returns_string_type(self):
        """AC #5: route function must return a string (not Command or other type)."""
        from pipeline.graph import route_after_execution
        result_success = route_after_execution(_make_state(execution_success=True))
        result_retry = route_after_execution(_make_state(execution_success=False, retry_count=1))
        result_replan = route_after_execution(_make_state(execution_success=False, retry_count=3))
        assert isinstance(result_success, str)
        assert isinstance(result_retry, str)
        assert isinstance(result_replan, str)

    def test_only_valid_destinations_returned(self):
        """AC #5: returned strings are in the valid destination set."""
        from pipeline.graph import route_after_execution
        valid = {"render_report", "generate_code", "generate_plan"}
        for retry_count in range(5):
            for success in [True, False]:
                state = _make_state(execution_success=success, retry_count=retry_count)
                result = route_after_execution(state)
                assert result in valid, f"Unexpected route destination: {result!r}"


# ---------------------------------------------------------------------------
# AC #3, #4, #6: handle_error node (pure function, no API calls)
# ---------------------------------------------------------------------------

class TestHandleError:
    """Tests for the handle_error node in pipeline/nodes/error_handler.py."""

    def test_increments_retry_count_from_zero(self):
        """AC #3: handle_error increments retry_count by 1."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0, replan_triggered=False)
        result = handle_error(state)
        assert result["retry_count"] == 1

    def test_increments_retry_count_from_one(self):
        """AC #3: handle_error increments retry_count from 1 to 2."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=1, replan_triggered=False)
        result = handle_error(state)
        assert result["retry_count"] == 2

    def test_sets_replan_triggered_at_threshold(self):
        """AC #4: retry_count 2 → 3 (>= 3) sets replan_triggered=True."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=2, replan_triggered=False)
        result = handle_error(state)
        assert result["retry_count"] == 3
        assert result["replan_triggered"] is True

    def test_does_not_set_replan_below_threshold(self):
        """AC #3: retry_count 0 → 1 does NOT set replan_triggered."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0, replan_triggered=False)
        result = handle_error(state)
        assert result["replan_triggered"] is False

    def test_does_not_set_replan_at_two(self):
        """AC #3: retry_count 1 → 2 does NOT set replan_triggered."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=1, replan_triggered=False)
        result = handle_error(state)
        assert result["replan_triggered"] is False

    def test_preserves_existing_error_messages(self):
        """AC #6: handle_error appends to error_messages — does not overwrite."""
        from pipeline.nodes.error_handler import handle_error
        prior = ["Previous error from executor."]
        state = _make_state(retry_count=0, error_messages=prior)
        result = handle_error(state)
        assert "Previous error from executor." in result["error_messages"]
        # Also has new message appended
        assert len(result["error_messages"]) > len(prior)

    def test_appends_to_empty_error_messages(self):
        """AC #6: handle_error adds message even when error_messages starts empty."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0, error_messages=[])
        result = handle_error(state)
        assert isinstance(result["error_messages"], list)
        assert len(result["error_messages"]) >= 1

    def test_returns_only_changed_keys(self):
        """LangGraph pattern: returned dict must contain only changed keys."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0)
        result = handle_error(state)
        # Must have retry_count, replan_triggered, error_messages
        assert "retry_count" in result
        assert "replan_triggered" in result
        assert "error_messages" in result

    def test_does_not_spread_full_state(self):
        """LangGraph pattern: pipeline state keys must NOT be leaked into result."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0)
        result = handle_error(state)
        ui_only_keys = {
            "user_query", "csv_temp_path", "data_row_count", "intent",
            "plan", "generated_code", "validation_errors",
            "execution_output", "execution_success",
            "report_charts", "report_text",
            "large_data_detected", "large_data_message", "recovery_applied",
        }
        leaked = set(result.keys()) & ui_only_keys
        assert not leaked, f"handle_error leaked state keys: {leaked}"

    def test_error_messages_are_strings(self):
        """AC #6: all error messages must be human-readable strings."""
        from pipeline.nodes.error_handler import handle_error
        state = _make_state(retry_count=0, error_messages=[])
        result = handle_error(state)
        for msg in result["error_messages"]:
            assert isinstance(msg, str)
            assert msg  # non-empty


# ---------------------------------------------------------------------------
# AC #1, #5: Graph structure and module boundary
# ---------------------------------------------------------------------------

class TestGraphStructure:
    """Tests for compiled graph structure and module boundaries."""

    def test_compiled_graph_is_importable(self):
        """AC #1: compiled_graph is importable and is a compiled LangGraph graph."""
        from pipeline.graph import compiled_graph
        assert compiled_graph is not None

    def test_run_pipeline_is_callable(self):
        """run_pipeline function exists and is callable."""
        from pipeline.graph import run_pipeline
        assert callable(run_pipeline)

    def test_graph_contains_required_nodes(self):
        """AC #1: compiled graph contains all required pipeline nodes."""
        from pipeline.graph import compiled_graph
        node_names = list(compiled_graph.nodes)
        required = [
            "classify_intent",
            "generate_plan",
            "generate_code",
            "validate_code_node",
            "execute_code",
            "render_report",
        ]
        for node in required:
            assert node in node_names, (
                f"Required node '{node}' not found in compiled graph. "
                f"Graph nodes: {node_names}"
            )

    def test_graph_no_streamlit_import(self):
        """Module boundary: graph.py must not import streamlit."""
        graph_path = (
            pathlib.Path(__file__).parent.parent / "pipeline" / "graph.py"
        )
        source = graph_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        streamlit_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "streamlit" in alias.name:
                        streamlit_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "streamlit" in node.module:
                    streamlit_imports.append(node.module)

        assert not streamlit_imports, (
            f"graph.py must not import streamlit, found: {streamlit_imports}"
        )

    def test_error_handler_no_streamlit_import(self):
        """Module boundary: error_handler.py must not import streamlit."""
        eh_path = (
            pathlib.Path(__file__).parent.parent / "pipeline" / "nodes" / "error_handler.py"
        )
        source = eh_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        streamlit_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "streamlit" in alias.name:
                        streamlit_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and "streamlit" in node.module:
                    streamlit_imports.append(node.module)

        assert not streamlit_imports, (
            f"error_handler.py must not import streamlit, found: {streamlit_imports}"
        )

    def test_route_after_execution_is_importable(self):
        """AC #5: route_after_execution function is importable from pipeline.graph."""
        from pipeline.graph import route_after_execution
        assert callable(route_after_execution)


# ---------------------------------------------------------------------------
# AC #5: Conditional edge map matches specification exactly (code inspection)
# ---------------------------------------------------------------------------

class TestConditionalEdgeSpec:
    """Verify the conditional edge call matches the architecture spec."""

    def test_add_conditional_edges_call_has_required_destinations(self):
        """AC #5: graph.add_conditional_edges called with render_report, generate_code, generate_plan."""
        graph_path = (
            pathlib.Path(__file__).parent.parent / "pipeline" / "graph.py"
        )
        source = graph_path.read_text(encoding="utf-8")

        # All three required destination strings must appear in graph.py
        required_destinations = ["render_report", "generate_code", "generate_plan"]
        for dest in required_destinations:
            assert f'"{dest}"' in source or f"'{dest}'" in source, (
                f"Required destination '{dest}' not found in graph.py source"
            )

        # add_conditional_edges must be called with "execute_code" as source
        assert '"execute_code"' in source or "'execute_code'" in source, (
            "graph.py must call add_conditional_edges with 'execute_code' as source node"
        )
