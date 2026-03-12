# pipeline/nodes/executor.py
"""Subprocess sandbox execution node.

Provides execute_code(state: PipelineState) -> dict, a LangGraph node that:
1. Creates a per-session temp directory via tempfile.mkdtemp().
2. Writes generated code to analysis.py inside the temp dir.
3. Copies the session CSV (if available) to data.csv in the temp dir.
4. Launches the code in a subprocess with restricted env (PATH + PYTHONPATH only)
   and a 60-second timeout.
5. Parses stdout for CHART:<base64_png> lines → list[bytes] in report_charts.
6. Cleans up the temp dir in a finally block (NFR12).
7. Returns only changed keys per LangGraph convention.

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
    environment (only PATH and PYTHONPATH inherited), then cleans up unconditionally.

    Parses CHART:<base64_png> lines from stdout into report_charts bytes.
    All other stdout becomes report_text.

    All exceptions are translated through translate_error() — never raw reprs.
    Returns only changed keys per LangGraph convention.
    """
    temp_dir = tempfile.mkdtemp()
    report_charts: list[bytes] = []
    report_text: str = ""
    execution_output: str = ""
    execution_success: bool = False
    existing_errors: list[str] = list(state.get("error_messages", []))
    new_errors: list[str] = []

    try:
        # Write generated code to a temp file inside the sandbox directory
        code_path = Path(temp_dir) / "analysis.py"
        code_path.write_text(state.get("generated_code", ""), encoding="utf-8")

        # Copy session CSV into temp dir so generated code can reference "data.csv"
        csv_source = state.get("csv_temp_path")
        if csv_source and Path(csv_source).exists():
            shutil.copy2(csv_source, Path(temp_dir) / "data.csv")

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

    return {
        "report_charts": report_charts,
        "report_text": report_text,
        "execution_output": execution_output,
        "execution_success": execution_success,
        "error_messages": existing_errors + new_errors,
    }
