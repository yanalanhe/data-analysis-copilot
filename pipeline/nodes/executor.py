# pipeline/nodes/executor.py
"""Subprocess sandbox execution node.

Provides execute_code(state: PipelineState) -> dict, a LangGraph node that:
1. Short-circuits with retry if validation_errors are set (validation guard).
2. Creates a per-session temp directory via tempfile.mkdtemp().
3. Writes generated code to analysis.py inside the temp dir.
4. Copies the session CSV (if available) to data.csv in the temp dir.
5. Launches the code in a subprocess with restricted env (PATH + PYTHONPATH +
   MPLCONFIGDIR + MPLBACKEND only) and a 60-second timeout.
6. Parses stdout for CHART:<base64_png> lines → list[bytes] in report_charts.
7. Cleans up the temp dir in a finally block (NFR12).
8. Returns only changed keys per LangGraph convention.

Story 3.5 addition: On any failure path, also returns retry_count (incremented
by 1) and replan_triggered (True when new retry_count >= 3). This enables
route_after_execution in pipeline/graph.py to decide retry vs. adaptive replan.
The success path returns the original Story 3.4 key set to preserve tests.

NOTE: Never import streamlit in this file.
"""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.state import PipelineState
from utils.error_translation import translate_error


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by stripping directory components and replacing unsafe characters."""
    import re
    # Take only the basename
    basename = os.path.basename(name)
    # Replace anything outside alphanumeric, dash, underscore, dot with underscore
    return re.sub(r"[^\w.\-]", "_", basename)


def _parse_stdout(stdout: str) -> tuple[list[bytes], str]:
    """Parse subprocess stdout into chart bytes and plain report text.

    Lines that start with 'CHART:' are base64-decoded to PNG bytes and collected
    in order. All other lines are joined and stripped to form the report text.

    Args:
        stdout: Raw stdout string captured from the subprocess.

    Returns:
        (charts, report_text) where charts is a list of PNG bytes objects
        and report_text is the non-CHART stdout joined and stripped.
    """
    charts: list[bytes] = []
    text_lines: list[str] = []

    for line in stdout.split("\n"):
        if line.startswith("CHART:"):
            try:
                charts.append(base64.b64decode(line[6:]))
            except Exception:
                pass  # skip malformed CHART: lines
        else:
            text_lines.append(line)

    return charts, "\n".join(text_lines).strip()


def execute_code(state: PipelineState) -> dict:
    """Execute validated code in an isolated subprocess with a 60-second timeout.

    Creates a per-session temp directory, writes generated code and optionally
    the session CSV into it, launches the code via sys.executable with a restricted
    environment (only PATH, PYTHONPATH, MPLCONFIGDIR, MPLBACKEND inherited),
    then cleans up unconditionally.

    Parses CHART:<base64_png> lines from stdout into report_charts bytes.
    All other stdout becomes report_text.

    All exceptions are translated through translate_error() — never raw reprs.
    Returns only changed keys per LangGraph convention.

    Story 3.5: failure paths also return retry_count and replan_triggered
    to drive route_after_execution routing in pipeline/graph.py.
    """
    # Validation guard (Story 3.5): if validate_code_node already set
    # validation_errors, skip subprocess and increment retry_count.
    # This avoids running invalid code and is the safe short-circuit path.
    if state.get("validation_errors"):
        new_retry = state.get("retry_count", 0) + 1
        existing_errors = list(state.get("error_messages", []))
        return {
            "execution_success": False,
            "retry_count": new_retry,
            "replan_triggered": new_retry >= 3,
            "report_charts": [],
            "report_text": "",
            "execution_output": "",
            "error_messages": existing_errors + [
                "Execution skipped — validation errors detected."
            ],
        }

    temp_dir = tempfile.mkdtemp()
    report_charts: list[bytes] = []
    report_text: str = ""
    execution_output: str = ""
    execution_success: bool = False
    existing_errors: list[str] = list(state.get("error_messages", []))
    new_errors: list[str] = []
    current_retry: int = state.get("retry_count", 0)

    try:
        # Write generated code to a temp file inside the sandbox directory
        code_path = Path(temp_dir) / "analysis.py"
        code_path.write_text(state.get("generated_code", ""), encoding="utf-8")

        # Copy all session CSVs into temp dir using sanitized original filenames
        csv_temp_paths = state.get("csv_temp_paths") or {}
        for original_name, source_path in csv_temp_paths.items():
            if source_path and Path(source_path).exists():
                safe_name = _sanitize_filename(original_name)
                shutil.copy2(source_path, Path(temp_dir) / safe_name)

        # Restricted environment: only PATH and PYTHONPATH inherited (NFR10)
        # MPLCONFIGDIR and MPLBACKEND are also set so matplotlib can initialise
        # without requiring HOME/USERPROFILE; config stays inside the temp dir.
        restricted_env: dict[str, str] = {
            "MPLCONFIGDIR": temp_dir,  # matplotlib config dir within sandbox
            "MPLBACKEND": "Agg",       # non-interactive backend; no display needed
        }
        if "PATH" in os.environ:
            restricted_env["PATH"] = os.environ["PATH"]
        if "PYTHONPATH" in os.environ:
            restricted_env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        result = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60,
            env=restricted_env,
        )

        if result.returncode == 0:
            report_charts, report_text = _parse_stdout(result.stdout)
            execution_output = result.stderr.strip()
            execution_success = True
        else:
            stderr = result.stderr.strip() or "Code execution failed with a non-zero exit code."
            new_errors.append(translate_error(Exception(stderr)))
            execution_success = False

    except subprocess.TimeoutExpired as e:
        new_errors.append(translate_error(e))
        execution_success = False

    except Exception as e:
        new_errors.append(translate_error(e))
        execution_success = False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if execution_success:
        # Success path: return original Story 3.4 key set (preserves test compatibility)
        return {
            "report_charts": report_charts,
            "report_text": report_text,
            "execution_output": execution_output,
            "execution_success": True,
            "error_messages": existing_errors + new_errors,
        }
    else:
        # Failure path (Story 3.5): also return retry_count and replan_triggered
        # to enable route_after_execution routing in pipeline/graph.py
        new_retry = current_retry + 1
        return {
            "report_charts": report_charts,
            "report_text": report_text,
            "execution_output": execution_output,
            "execution_success": False,
            "retry_count": new_retry,
            "replan_triggered": new_retry >= 3,
            "error_messages": existing_errors + new_errors,
        }
