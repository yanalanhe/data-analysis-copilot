# tests/test_editable_code.py
"""Unit tests for Story 5.2: Editable Code & Manual Re-Execution.

Tests cover:
1. build_reexec_state() helper logic (Tasks 2.1-2.2)
2. Validation gate: validate_code_node detects bad code → execute_code NOT called (Task 2.3)
3. Success path: valid code → execute_code → report_charts/report_text populated (Task 2.4)
4. Failure path: bad runtime code → execution_success=False, translated error_messages (Task 2.5)
"""
from pipeline.nodes.executor import execute_code
from pipeline.nodes.validator import validate_code_node
from utils.reexec import build_reexec_state


def _make_pipeline_state(**overrides) -> dict:
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales trend",
        "csv_temp_path": None,
        "data_row_count": 100,
        "intent": "report",
        "plan": ["Load data", "Plot chart"],
        "generated_code": "print('old code')",
        "validation_errors": ["some old error"],
        "execution_output": "old output",
        "execution_success": True,
        "retry_count": 2,
        "replan_triggered": True,
        "error_messages": ["old error message"],
        "report_charts": [b"old_chart"],
        "report_text": "old report text",
        "large_data_detected": False,
        "large_data_message": "",
        "recovery_applied": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Task 2.1 — _build_reexec_state resets execution fields, preserves context
# ---------------------------------------------------------------------------

class TestBuildReexecState:
    """Tests for the re-execution state builder (mirrors streamlit_app.py::_build_reexec_state)."""

    def test_generated_code_is_overridden_with_edited_code(self):
        """Task 2.1: generated_code is set to the edited_code value."""
        ps = _make_pipeline_state(generated_code="old code")
        result = build_reexec_state(ps, "new edited code")
        assert result["generated_code"] == "new edited code"

    def test_retry_count_reset_to_zero(self):
        """Task 2.1: retry_count is reset to 0 regardless of previous value."""
        ps = _make_pipeline_state(retry_count=3)
        result = build_reexec_state(ps, "print('x')")
        assert result["retry_count"] == 0

    def test_validation_errors_cleared(self):
        """Task 2.1: validation_errors is reset to empty list."""
        ps = _make_pipeline_state(validation_errors=["bad import", "syntax error"])
        result = build_reexec_state(ps, "print('x')")
        assert result["validation_errors"] == []

    def test_error_messages_cleared(self):
        """Task 2.1: error_messages is reset to empty list."""
        ps = _make_pipeline_state(error_messages=["An unexpected error occurred."])
        result = build_reexec_state(ps, "print('x')")
        assert result["error_messages"] == []

    def test_report_charts_cleared(self):
        """Task 2.1: report_charts is reset to empty list."""
        ps = _make_pipeline_state(report_charts=[b"old_chart_bytes"])
        result = build_reexec_state(ps, "print('x')")
        assert result["report_charts"] == []

    def test_report_text_cleared(self):
        """Task 2.1: report_text is reset to empty string."""
        ps = _make_pipeline_state(report_text="old trend analysis")
        result = build_reexec_state(ps, "print('x')")
        assert result["report_text"] == ""

    def test_csv_temp_path_preserved(self):
        """Task 2.1: csv_temp_path is preserved from original state."""
        ps = _make_pipeline_state(csv_temp_path="/tmp/uploads/data.csv")
        result = build_reexec_state(ps, "print('x')")
        assert result["csv_temp_path"] == "/tmp/uploads/data.csv"

    def test_user_query_preserved(self):
        """Task 2.1: user_query is preserved from original state."""
        ps = _make_pipeline_state(user_query="show monthly revenue")
        result = build_reexec_state(ps, "print('x')")
        assert result["user_query"] == "show monthly revenue"

    def test_plan_preserved(self):
        """Task 2.1: plan is preserved from original state."""
        plan = ["Step 1: load CSV", "Step 2: plot bar chart"]
        ps = _make_pipeline_state(plan=plan)
        result = build_reexec_state(ps, "print('x')")
        assert result["plan"] == plan


# ---------------------------------------------------------------------------
# Task 2.2 — execution_success and replan_triggered always reset
# ---------------------------------------------------------------------------

class TestBuildReexecStateEdgeCases:
    """Edge case tests for build_reexec_state."""

    def test_none_edited_code_falls_back_to_original_generated_code(self):
        """M1 fix: st_ace returns None on initial render — must fall back to original code."""
        ps = _make_pipeline_state(generated_code="original code")
        result = build_reexec_state(ps, None)
        assert result["generated_code"] == "original code"

    def test_undocumented_keys_not_preserved(self):
        """M3 fix: only documented preserved keys pass through, not arbitrary extras."""
        ps = _make_pipeline_state()
        ps["unexpected_future_key"] = "should not survive"
        result = build_reexec_state(ps, "print('x')")
        assert "unexpected_future_key" not in result


class TestBuildReexecStateResets:
    """Tests that execution_success and replan_triggered are always reset."""

    def test_execution_success_reset_to_false_when_was_true(self):
        """Task 2.2: execution_success=False regardless of original True value."""
        ps = _make_pipeline_state(execution_success=True)
        result = build_reexec_state(ps, "print('x')")
        assert result["execution_success"] is False

    def test_replan_triggered_reset_to_false_when_was_true(self):
        """Task 2.2: replan_triggered=False regardless of original True value."""
        ps = _make_pipeline_state(replan_triggered=True)
        result = build_reexec_state(ps, "print('x')")
        assert result["replan_triggered"] is False

    def test_execution_output_reset_to_empty_string(self):
        """Task 2.2: execution_output is reset to empty string."""
        ps = _make_pipeline_state(execution_output="old stdout")
        result = build_reexec_state(ps, "print('x')")
        assert result["execution_output"] == ""


# ---------------------------------------------------------------------------
# Task 2.3 — Validation gate: bad code → validation_errors non-empty
# ---------------------------------------------------------------------------

class TestReexecValidationGate:
    """Tests that validate_code_node catches unsafe/invalid code before execution."""

    def test_validate_code_node_detects_blocked_import(self):
        """Task 2.3: Code using 'os' namespace is flagged by validate_code_node.

        The validation gate: if val_result.get('validation_errors'), do NOT execute.
        """
        ps = _make_pipeline_state(generated_code="import os\nos.system('rm -rf /')")
        re_exec_state = build_reexec_state(ps, "import os\nos.system('rm -rf /')")

        val_result = validate_code_node(re_exec_state)

        # Validation errors must be non-empty → execution must NOT proceed
        assert val_result.get("validation_errors"), (
            "Expected validation_errors to be non-empty for 'os' namespace usage"
        )
        # Human-readable translated errors must also be present
        assert val_result.get("error_messages"), (
            "Expected error_messages to contain translated user-facing error"
        )
        # No raw traceback — message should be a plain English string
        for msg in val_result.get("error_messages", []):
            assert "Traceback" not in msg, "Raw traceback must not appear in error_messages"

    def test_validate_code_node_detects_syntax_error(self):
        """Task 2.3: Code with syntax error is flagged by validate_code_node."""
        bad_code = "def foo(\n    x\n# missing closing paren"
        ps = _make_pipeline_state(generated_code=bad_code)
        re_exec_state = build_reexec_state(ps, bad_code)

        val_result = validate_code_node(re_exec_state)

        assert val_result.get("validation_errors"), "Expected validation_errors for syntax error"

    def test_validate_code_node_clears_errors_for_valid_code(self):
        """Task 2.3: Valid pandas code passes validation — returns empty validation_errors."""
        valid_code = "import pandas as pd\nresult = pd.DataFrame({'a': [1, 2]})"
        ps = _make_pipeline_state(generated_code=valid_code)
        re_exec_state = build_reexec_state(ps, valid_code)

        val_result = validate_code_node(re_exec_state)

        assert val_result.get("validation_errors") == [], (
            "Expected no validation_errors for valid pandas code"
        )


# ---------------------------------------------------------------------------
# Task 2.4 — Re-execution success path
# ---------------------------------------------------------------------------

class TestReexecSuccessPath:
    """Tests the success path: validate → execute → report populated."""

    def test_successful_execution_sets_execution_success_true(self):
        """Task 2.4: Valid code that runs cleanly → execution_success=True."""
        valid_code = "print('analysis complete')"
        ps = _make_pipeline_state(generated_code=valid_code)
        re_exec_state = build_reexec_state(ps, valid_code)

        # Validate first (must pass)
        val_result = validate_code_node(re_exec_state)
        assert not val_result.get("validation_errors"), "Validation should pass for this code"

        # Execute
        merged = {**re_exec_state, **val_result}
        exec_result = execute_code(merged)
        final_state = {**merged, **exec_result}

        assert final_state["execution_success"] is True

    def test_successful_execution_populates_report_text(self):
        """Task 2.4: Printed output is captured in report_text after execution."""
        valid_code = "print('trend: revenue increased 12%')"
        ps = _make_pipeline_state(generated_code=valid_code)
        re_exec_state = build_reexec_state(ps, valid_code)

        val_result = validate_code_node(re_exec_state)
        merged = {**re_exec_state, **val_result}
        exec_result = execute_code(merged)
        final_state = {**merged, **exec_result}

        assert "trend: revenue increased 12%" in final_state["report_text"]

    def test_successful_execution_preserves_edited_code_in_state(self):
        """Task 2.4: generated_code in final_state equals the edited code submitted."""
        edited_code = "print('edited version')"
        ps = _make_pipeline_state()
        re_exec_state = build_reexec_state(ps, edited_code)

        val_result = validate_code_node(re_exec_state)
        merged = {**re_exec_state, **val_result}
        exec_result = execute_code(merged)
        final_state = {**merged, **exec_result}

        # execute_code does not overwrite generated_code — edited version is preserved
        assert final_state["generated_code"] == edited_code


# ---------------------------------------------------------------------------
# Task 2.5 — Re-execution failure path (runtime error)
# ---------------------------------------------------------------------------

class TestReexecFailurePath:
    """Tests the failure path: valid-looking code that fails at runtime."""

    def test_runtime_error_sets_execution_success_false(self):
        """Task 2.5: Code that raises an unhandled exception → execution_success=False."""
        # AST-valid code (passes validation) but raises RuntimeError at execution
        bad_runtime_code = "result = int('not_a_number')"
        ps = _make_pipeline_state(generated_code=bad_runtime_code)
        re_exec_state = build_reexec_state(ps, bad_runtime_code)

        val_result = validate_code_node(re_exec_state)
        assert not val_result.get("validation_errors"), "This code should pass AST validation"

        merged = {**re_exec_state, **val_result}
        exec_result = execute_code(merged)
        final_state = {**merged, **exec_result}

        assert final_state["execution_success"] is False

    def test_runtime_error_populates_error_messages(self):
        """Task 2.5: Runtime failure → error_messages contains translated message (no raw traceback)."""
        bad_runtime_code = "result = int('not_a_number')"
        ps = _make_pipeline_state(generated_code=bad_runtime_code)
        re_exec_state = build_reexec_state(ps, bad_runtime_code)

        val_result = validate_code_node(re_exec_state)
        merged = {**re_exec_state, **val_result}
        exec_result = execute_code(merged)
        final_state = {**merged, **exec_result}

        assert final_state["error_messages"], "error_messages must not be empty on runtime failure"
        for msg in final_state["error_messages"]:
            assert isinstance(msg, str), "Each error message must be a string"
            # Must not be a raw traceback line
            assert not msg.startswith("Traceback (most recent call last)"), (
                "Raw traceback must not appear — use translate_error() via execute_code"
            )
