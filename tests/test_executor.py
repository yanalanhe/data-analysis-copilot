# tests/test_executor.py
"""Integration tests for pipeline/nodes/executor.py — subprocess sandbox execution.

These are real subprocess integration tests (no subprocess mocking for most tests).
The subprocess is a key security boundary; real execution validates actual isolation.
Timeout tests use mock.patch to avoid waiting 60+ seconds in CI.

Covers Story 3.4 ACs #1–6.
"""
import ast
import base64
import io
import os
import pathlib
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

from pipeline.nodes.executor import _parse_stdout, execute_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales over time",
        "csv_temp_paths": {},
        "csv_metadata": "",
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


# Minimal chart-producing code: uses Agg backend (no display needed) and outputs CHART: line
_CHART_CODE = """\
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import io

plt.figure()
plt.plot([1, 2, 3], [4, 5, 6])
plt.xlabel('X axis')
plt.ylabel('Y axis')
plt.title('Test Chart')
plt.tight_layout()

buf = io.BytesIO()
plt.savefig(buf, format='png', bbox_inches='tight')
buf.seek(0)
print("CHART:" + base64.b64encode(buf.getvalue()).decode())
print("Trend: values are increasing.")
"""

# Two charts: prints two CHART: lines + one text line
_MULTI_CHART_CODE = """\
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import io

for i in range(2):
    plt.figure()
    plt.plot([1, 2], [i, i + 1])
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title(f'Chart {i}')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    print("CHART:" + base64.b64encode(buf.getvalue()).decode())

print("Two charts generated.")
"""

# Text-only code: no CHART: lines
_TEXT_ONLY_CODE = """\
print("Summary: average is 42.")
print("No charts here.")
"""

# Failing code: exits with non-zero return code
_FAILING_CODE = """\
import sys
sys.exit(1)
"""

# Env leak test: tries to read a custom env var that should NOT be visible
_ENV_LEAK_CODE = """\
import os
val = os.environ.get("_EXECUTOR_TEST_SECRET_", "NOT_FOUND")
print(val)
"""

# Empty code: no output, exit 0
_EMPTY_CODE = ""

# Code that produces only whitespace text (should result in empty report_text)
_WHITESPACE_TEXT_CODE = """\
print("   ")
print("")
"""


# ---------------------------------------------------------------------------
# Unit tests for _parse_stdout helper
# ---------------------------------------------------------------------------

class TestParseStdout:
    """Unit tests for the internal _parse_stdout helper."""

    def test_chart_line_decoded_to_bytes(self):
        raw_png = b"fakepngbytes"
        b64 = base64.b64encode(raw_png).decode()
        charts, text = _parse_stdout(f"CHART:{b64}\n")
        assert len(charts) == 1
        assert charts[0] == raw_png

    def test_text_line_goes_to_report_text(self):
        charts, text = _parse_stdout("Hello world\nSecond line\n")
        assert charts == []
        assert "Hello world" in text
        assert "Second line" in text

    def test_chart_lines_not_in_report_text(self):
        raw_png = b"png"
        b64 = base64.b64encode(raw_png).decode()
        charts, text = _parse_stdout(f"CHART:{b64}\nsome text\n")
        assert "CHART:" not in text

    def test_multiple_chart_lines(self):
        raw1, raw2 = b"png1", b"png2"
        b64_1 = base64.b64encode(raw1).decode()
        b64_2 = base64.b64encode(raw2).decode()
        charts, text = _parse_stdout(f"CHART:{b64_1}\nCHART:{b64_2}\ntext\n")
        assert len(charts) == 2
        assert charts[0] == raw1
        assert charts[1] == raw2

    def test_empty_stdout(self):
        charts, text = _parse_stdout("")
        assert charts == []
        assert text == ""

    def test_report_text_is_stripped(self):
        charts, text = _parse_stdout("  \n  hello  \n  \n")
        assert text == "hello"

    def test_malformed_chart_line_skipped(self):
        """H1 fix: malformed base64 after CHART: is silently skipped."""
        valid_b64 = base64.b64encode(b"validpng").decode()
        stdout = f"CHART:!!!invalid-base64!!!\nCHART:{valid_b64}\nsome text\n"
        charts, text = _parse_stdout(stdout)
        assert len(charts) == 1
        assert charts[0] == b"validpng"
        assert "some text" in text

    def test_only_chart_lines_yields_empty_text(self):
        b64 = base64.b64encode(b"png").decode()
        charts, text = _parse_stdout(f"CHART:{b64}\n")
        assert text == ""


# ---------------------------------------------------------------------------
# AC #1–2: Temp dir creation and subprocess execution (success scenarios)
# ---------------------------------------------------------------------------

class TestExecuteCodeSuccess:
    """Integration tests for successful subprocess execution."""

    def test_single_chart_success(self):
        """AC #1, #4: successful execution with one CHART: line."""
        state = _make_state(generated_code=_CHART_CODE)
        result = execute_code(state)

        assert result["execution_success"] is True
        assert len(result["report_charts"]) == 1
        # Decoded value should be valid PNG bytes (starts with PNG magic number)
        assert result["report_charts"][0][:4] == b"\x89PNG"
        assert "Trend: values are increasing." in result["report_text"]
        assert result["error_messages"] == []

    def test_text_only_success(self):
        """AC #4: no CHART: lines → report_charts empty, report_text populated."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE)
        result = execute_code(state)

        assert result["execution_success"] is True
        assert result["report_charts"] == []
        assert "Summary: average is 42." in result["report_text"]

    def test_multiple_charts_success(self):
        """AC #4: multiple CHART: lines → all collected in order."""
        state = _make_state(generated_code=_MULTI_CHART_CODE)
        result = execute_code(state)

        assert result["execution_success"] is True
        assert len(result["report_charts"]) == 2
        for chart in result["report_charts"]:
            assert chart[:4] == b"\x89PNG"
        assert "Two charts generated." in result["report_text"]

    def test_empty_code_exits_success(self):
        """Edge case: empty generated_code → exit 0, empty output."""
        state = _make_state(generated_code=_EMPTY_CODE)
        result = execute_code(state)

        assert result["execution_success"] is True
        assert result["report_charts"] == []
        assert result["report_text"] == ""

    def test_report_text_excludes_chart_lines(self):
        """AC #4: CHART: prefix lines must NOT appear in report_text."""
        state = _make_state(generated_code=_CHART_CODE)
        result = execute_code(state)

        assert "CHART:" not in result["report_text"]

    def test_report_text_is_stripped(self):
        """AC #4: report_text should have no leading/trailing whitespace."""
        state = _make_state(generated_code=_WHITESPACE_TEXT_CODE)
        result = execute_code(state)

        assert result["execution_success"] is True
        assert result["report_text"] == ""


# ---------------------------------------------------------------------------
# AC #5: Failure scenarios (non-zero exit, stderr)
# ---------------------------------------------------------------------------

class TestExecuteCodeFailure:
    """Integration tests for failure scenarios."""

    def test_non_zero_exit_sets_failure(self):
        """AC #5: non-zero exit → execution_success False, error in error_messages."""
        state = _make_state(generated_code=_FAILING_CODE)
        result = execute_code(state)

        assert result["execution_success"] is False
        assert result["report_charts"] == []
        assert len(result["error_messages"]) >= 1

    def test_runtime_exception_in_code(self):
        """AC #5: code that raises an unhandled exception → execution_success False."""
        bad_code = "raise ValueError('intentional test error')"
        state = _make_state(generated_code=bad_code)
        result = execute_code(state)

        assert result["execution_success"] is False
        assert result["error_messages"]

    def test_existing_error_messages_preserved(self):
        """AC #5: pre-existing error_messages are preserved (not overwritten)."""
        prior_errors = ["Prior error from validation step."]
        state = _make_state(
            generated_code=_FAILING_CODE,
            error_messages=prior_errors,
        )
        result = execute_code(state)

        assert "Prior error from validation step." in result["error_messages"]
        assert len(result["error_messages"]) >= 2  # prior + new

    def test_failure_error_message_is_translated(self):
        """AC #5: error message must be a human-readable string, not raw repr."""
        state = _make_state(generated_code=_FAILING_CODE)
        result = execute_code(state)

        for msg in result["error_messages"]:
            assert isinstance(msg, str)
            assert msg  # non-empty


# ---------------------------------------------------------------------------
# AC #3: Timeout handling
# ---------------------------------------------------------------------------

class TestExecuteCodeTimeout:
    """Tests for 60-second timeout enforcement."""

    def test_timeout_sets_failure(self):
        """AC #3: TimeoutExpired → execution_success False, translated error."""
        with mock.patch(
            "pipeline.nodes.executor.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=sys.executable, timeout=60),
        ):
            state = _make_state(generated_code="import time; time.sleep(999)")
            result = execute_code(state)

        assert result["execution_success"] is False
        assert len(result["error_messages"]) >= 1
        # Translated message must match the error taxonomy
        assert result["error_messages"][-1] == (
            "Analysis took too long and was stopped. "
            "Try a simpler request or subset your data."
        )

    def test_timeout_produces_empty_charts(self):
        """AC #3: timeout before any output → report_charts empty."""
        with mock.patch(
            "pipeline.nodes.executor.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=sys.executable, timeout=60),
        ):
            state = _make_state(generated_code="import time; time.sleep(999)")
            result = execute_code(state)

        assert result["report_charts"] == []


# ---------------------------------------------------------------------------
# AC #6: Temp dir cleanup
# ---------------------------------------------------------------------------

class TestExecuteCodeCleanup:
    """Tests that temp directories are always cleaned up (NFR12)."""

    def test_temp_dir_deleted_after_success(self):
        """AC #6: temp dir is gone after successful execution."""
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def capturing_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_dirs.append(d)
            return d

        with mock.patch("pipeline.nodes.executor.tempfile.mkdtemp", side_effect=capturing_mkdtemp):
            state = _make_state(generated_code=_TEXT_ONLY_CODE)
            execute_code(state)

        assert created_dirs, "mkdtemp should have been called"
        for d in created_dirs:
            assert not os.path.exists(d), f"Temp dir {d!r} was not cleaned up"

    def test_temp_dir_deleted_after_failure(self):
        """AC #6: temp dir is gone even after execution failure."""
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def capturing_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_dirs.append(d)
            return d

        with mock.patch("pipeline.nodes.executor.tempfile.mkdtemp", side_effect=capturing_mkdtemp):
            state = _make_state(generated_code=_FAILING_CODE)
            execute_code(state)

        assert created_dirs, "mkdtemp should have been called"
        for d in created_dirs:
            assert not os.path.exists(d), f"Temp dir {d!r} was not cleaned up after failure"

    def test_temp_dir_deleted_after_timeout(self):
        """AC #6: temp dir is gone after a timeout (finally block runs)."""
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def capturing_mkdtemp(**kwargs):
            d = original_mkdtemp(**kwargs)
            created_dirs.append(d)
            return d

        with mock.patch("pipeline.nodes.executor.tempfile.mkdtemp", side_effect=capturing_mkdtemp):
            with mock.patch(
                "pipeline.nodes.executor.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=sys.executable, timeout=60),
            ):
                state = _make_state(generated_code="")
                execute_code(state)

        assert created_dirs
        for d in created_dirs:
            assert not os.path.exists(d), f"Temp dir {d!r} not cleaned up after timeout"


# ---------------------------------------------------------------------------
# AC #2: Environment variable isolation (NFR9, NFR10)
# ---------------------------------------------------------------------------

class TestExecuteCodeEnvIsolation:
    """Tests that subprocess cannot access host environment variables."""

    def test_subprocess_cannot_see_secret_env_var(self):
        """AC #2 (NFR10): subprocess env is restricted; host vars are not inherited."""
        secret_key = "_EXECUTOR_TEST_SECRET_"
        secret_value = "super_secret_value_12345"

        # Set a secret in the current process env
        os.environ[secret_key] = secret_value
        try:
            state = _make_state(generated_code=_ENV_LEAK_CODE)
            result = execute_code(state)
        finally:
            os.environ.pop(secret_key, None)

        # If env isolation works, the subprocess should print "NOT_FOUND"
        assert result["execution_success"] is True
        assert "NOT_FOUND" in result["report_text"]
        assert secret_value not in result["report_text"]

    def test_subprocess_env_contains_only_path_and_pythonpath(self):
        """AC #2 (NFR10): verify restricted env is passed to subprocess.run."""
        captured_calls = []

        original_run = subprocess.run

        def capturing_run(*args, **kwargs):
            captured_calls.append(kwargs.get("env", {}))
            # Actually run the subprocess for a real result
            return original_run(*args, **kwargs)

        with mock.patch("pipeline.nodes.executor.subprocess.run", side_effect=capturing_run):
            state = _make_state(generated_code=_TEXT_ONLY_CODE)
            execute_code(state)

        assert captured_calls, "subprocess.run should have been called"
        env_passed = captured_calls[0]
        # PATH and PYTHONPATH for execution; MPLCONFIGDIR/MPLBACKEND for matplotlib
        # isolation (keeps config inside temp dir, no HOME/USERPROFILE leakage needed)
        allowed_keys = {"PATH", "PYTHONPATH", "MPLCONFIGDIR", "MPLBACKEND"}
        extra_keys = set(env_passed.keys()) - allowed_keys
        assert not extra_keys, f"Unexpected env keys passed to subprocess: {extra_keys}"


# ---------------------------------------------------------------------------
# Return structure and module guard
# ---------------------------------------------------------------------------

class TestExecuteCodeReturnStructure:
    """Tests for return dict structure compliance and module boundary guard."""

    def test_returns_only_changed_keys(self):
        """AC #4: return dict contains exactly the expected changed keys."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE)
        result = execute_code(state)

        expected_keys = {"report_charts", "report_text", "execution_output", "execution_success", "error_messages"}
        assert set(result.keys()) == expected_keys

    def test_does_not_spread_full_state(self):
        """LangGraph pattern: state-only keys must NOT appear in returned dict."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE)
        result = execute_code(state)

        pipeline_only_keys = {
            "user_query", "csv_temp_paths", "csv_metadata", "intent",
            "plan", "generated_code", "validation_errors",
            "retry_count", "replan_triggered", "large_data_detected",
            "large_data_message", "recovery_applied",
        }
        leaked = set(result.keys()) & pipeline_only_keys
        assert not leaked, f"Returned dict leaked these state keys: {leaked}"

    def test_executor_no_streamlit_import(self):
        """Module boundary guard: executor.py must not import streamlit."""
        executor_path = (
            pathlib.Path(__file__).parent.parent / "pipeline" / "nodes" / "executor.py"
        )
        source = executor_path.read_text(encoding="utf-8")
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
            f"executor.py must not import streamlit, found: {streamlit_imports}"
        )

    def test_csv_file_copied_and_readable(self):
        """AC #1: CSV is copied into temp dir using original filename and readable by subprocess."""
        csv_code = 'import pandas as pd\ndf = pd.read_csv("data.csv")\nprint(f"rows={len(df)}")\n'
        # Create a real CSV temp file
        csv_tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        )
        try:
            csv_tmp.write("a,b\n1,2\n3,4\n")
            csv_tmp.close()
            state = _make_state(
                generated_code=csv_code,
                csv_temp_paths={"data.csv": csv_tmp.name}
            )
            result = execute_code(state)
        finally:
            os.unlink(csv_tmp.name)

        assert result["execution_success"] is True
        assert "rows=2" in result["report_text"]

    def test_csv_temp_paths_empty_does_not_crash(self):
        """Edge case: csv_temp_paths={} (no files) → no CSV copy, subprocess still runs."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE, csv_temp_paths={})
        result = execute_code(state)
        # Should not crash and should succeed (code doesn't use CSV)
        assert result["execution_success"] is True

    def test_csv_temp_paths_missing_file_does_not_crash(self):
        """Edge case: csv_temp_paths entry points to nonexistent file → no crash."""
        state = _make_state(
            generated_code=_TEXT_ONLY_CODE,
            csv_temp_paths={"missing.csv": "/nonexistent/path/data.csv"},
        )
        result = execute_code(state)
        assert result["execution_success"] is True


# ---------------------------------------------------------------------------
# Story 3.5: Validation guard and failure path return structure
# ---------------------------------------------------------------------------

class TestExecuteCodeValidationGuard:
    """Tests for the validation guard that skips subprocess on validation errors."""

    def test_validation_guard_skips_execution_on_errors(self):
        """Validation guard: non-empty validation_errors → execution_success=False, no subprocess."""
        state = _make_state(
            generated_code="import os\nos.system('rm -rf /')",
            validation_errors=["Blocked import: os"],
        )
        result = execute_code(state)
        assert result["execution_success"] is False

    def test_validation_guard_returns_empty_charts_and_text(self):
        """Validation guard returns empty report_charts and report_text."""
        state = _make_state(
            generated_code="bad code",
            validation_errors=["Syntax error"],
        )
        result = execute_code(state)
        assert result["report_charts"] == []
        assert result["report_text"] == ""
        assert result["execution_output"] == ""

    def test_validation_guard_increments_retry_count(self):
        """Validation guard increments retry_count by 1."""
        state = _make_state(
            generated_code="bad",
            validation_errors=["error"],
            retry_count=1,
        )
        result = execute_code(state)
        assert result["retry_count"] == 2

    def test_validation_guard_sets_replan_at_threshold(self):
        """Validation guard sets replan_triggered=True when retry_count reaches 3."""
        state = _make_state(
            generated_code="bad",
            validation_errors=["error"],
            retry_count=2,
        )
        result = execute_code(state)
        assert result["retry_count"] == 3
        assert result["replan_triggered"] is True

    def test_validation_guard_no_replan_below_threshold(self):
        """Validation guard: retry_count 0→1 does not trigger replan."""
        state = _make_state(
            generated_code="bad",
            validation_errors=["error"],
            retry_count=0,
        )
        result = execute_code(state)
        assert result["retry_count"] == 1
        assert result["replan_triggered"] is False

    def test_validation_guard_preserves_existing_errors(self):
        """Validation guard preserves existing error_messages."""
        prior = ["Previous error from codegen."]
        state = _make_state(
            generated_code="bad",
            validation_errors=["Syntax error"],
            error_messages=prior,
        )
        result = execute_code(state)
        assert "Previous error from codegen." in result["error_messages"]

    def test_validation_guard_adds_context_message(self):
        """Validation guard adds its own context message to error_messages."""
        state = _make_state(
            generated_code="bad",
            validation_errors=["Blocked import: os"],
            error_messages=["Blocked import: os"],
        )
        result = execute_code(state)
        # Should have the original error plus the guard's context message
        assert len(result["error_messages"]) > 1

    def test_empty_validation_errors_proceeds_normally(self):
        """Empty validation_errors list does NOT trigger the guard."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE, validation_errors=[])
        result = execute_code(state)
        assert result["execution_success"] is True


class TestExecuteCodeFailureReturnStructure:
    """Tests for failure path return structure (Story 3.5 additions)."""

    def test_failure_returns_retry_count(self):
        """Failure path includes retry_count in return dict."""
        state = _make_state(generated_code=_FAILING_CODE, retry_count=0)
        result = execute_code(state)
        assert result["execution_success"] is False
        assert "retry_count" in result
        assert result["retry_count"] == 1

    def test_failure_increments_retry_from_existing(self):
        """Failure path increments retry_count from existing value."""
        state = _make_state(generated_code=_FAILING_CODE, retry_count=2)
        result = execute_code(state)
        assert result["retry_count"] == 3

    def test_failure_sets_replan_triggered_at_threshold(self):
        """Failure path sets replan_triggered=True when new retry_count >= 3."""
        state = _make_state(generated_code=_FAILING_CODE, retry_count=2)
        result = execute_code(state)
        assert result["replan_triggered"] is True

    def test_failure_no_replan_below_threshold(self):
        """Failure path: replan_triggered=False when new retry_count < 3."""
        state = _make_state(generated_code=_FAILING_CODE, retry_count=0)
        result = execute_code(state)
        assert result["replan_triggered"] is False

    def test_success_does_not_include_retry_keys(self):
        """Success path must NOT include retry_count or replan_triggered."""
        state = _make_state(generated_code=_TEXT_ONLY_CODE)
        result = execute_code(state)
        assert result["execution_success"] is True
        assert "retry_count" not in result
        assert "replan_triggered" not in result
