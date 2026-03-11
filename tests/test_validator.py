# tests/test_validator.py
"""Unit tests for the AST allowlist code validator.

Tests validate_code(code: str) -> tuple[bool, list[str]] directly.
All tests are pure logic tests — no mocking needed since validate_code
never executes code; it only parses the AST.
"""
import ast
import pathlib

import pytest

from pipeline.nodes.validator import validate_code, validate_code_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales over time",
        "csv_temp_path": "/tmp/test.csv",
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
# AC #5: Valid clean code returns (True, [])
# ---------------------------------------------------------------------------

def test_valid_clean_code_returns_true():
    code = (
        "import pandas as pd\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "import base64\n"
        "import io\n"
        "\n"
        "df = pd.read_csv(csv_path)\n"
        "buf = io.BytesIO()\n"
        "plt.plot(df['x'], df['y'])\n"
        "plt.xlabel('X Values')\n"
        "plt.ylabel('Y Values')\n"
        "plt.title('Test Chart')\n"
        "plt.tight_layout()\n"
        "plt.savefig(buf, format='png', bbox_inches='tight')\n"
        "plt.close()\n"
        "print('CHART:' + base64.b64encode(buf.getvalue()).decode())\n"
    )
    is_valid, errors = validate_code(code)
    assert is_valid is True
    assert errors == []


def test_empty_string_returns_valid():
    """Empty code has no imports and no blocked ops — valid."""
    is_valid, errors = validate_code("")
    assert is_valid is True
    assert errors == []


def test_simple_pandas_numpy_code_valid():
    code = (
        "import pandas as pd\n"
        "import numpy as np\n"
        "\n"
        "df = pd.read_csv(csv_path)\n"
        "mean = np.mean(df['value'])\n"
        "print(f'Mean: {mean}')\n"
    )
    is_valid, errors = validate_code(code)
    assert is_valid is True
    assert errors == []


# ---------------------------------------------------------------------------
# AC #2: Syntax error returns (False, ["Syntax error: ..."])
# ---------------------------------------------------------------------------

def test_syntax_error_returns_false():
    code = "def broken(:\n    pass"
    is_valid, errors = validate_code(code)
    assert is_valid is False
    assert len(errors) == 1
    assert errors[0].startswith("Syntax error:")


def test_syntax_error_stops_at_parse():
    """validate_code must return immediately on syntax error — no further checks."""
    # This code has a syntax error before any blocked imports
    code = "def bad(:\n    import os"
    is_valid, errors = validate_code(code)
    assert is_valid is False
    # Only the syntax error should be reported, not the blocked import
    assert len(errors) == 1
    assert errors[0].startswith("Syntax error:")


# ---------------------------------------------------------------------------
# AC #3: Blocked imports return (False, [error_message])
# ---------------------------------------------------------------------------

class TestBlockedImports:
    def test_import_os_blocked(self):
        is_valid, errors = validate_code("import os")
        assert is_valid is False
        assert any("os" in e for e in errors)

    def test_import_socket_blocked(self):
        is_valid, errors = validate_code("import socket")
        assert is_valid is False
        assert any("socket" in e for e in errors)

    def test_import_subprocess_blocked(self):
        is_valid, errors = validate_code("import subprocess")
        assert is_valid is False
        assert any("subprocess" in e for e in errors)

    def test_import_urllib_blocked(self):
        is_valid, errors = validate_code("import urllib")
        assert is_valid is False
        assert any("urllib" in e for e in errors)

    def test_import_requests_blocked(self):
        is_valid, errors = validate_code("import requests")
        assert is_valid is False
        assert any("requests" in e for e in errors)

    def test_import_sys_blocked(self):
        is_valid, errors = validate_code("import sys")
        assert is_valid is False
        assert any("sys" in e for e in errors)

    def test_from_os_import_path_blocked(self):
        is_valid, errors = validate_code("from os import path")
        assert is_valid is False
        assert any("os" in e for e in errors)

    def test_from_os_path_import_join_blocked(self):
        is_valid, errors = validate_code("from os.path import join")
        assert is_valid is False
        assert any("os" in e for e in errors)

    def test_import_shutil_blocked(self):
        """Any import not in the allowlist is blocked."""
        is_valid, errors = validate_code("import shutil")
        assert is_valid is False

    def test_import_json_blocked(self):
        """json is not in the allowlist."""
        is_valid, errors = validate_code("import json")
        assert is_valid is False


# ---------------------------------------------------------------------------
# AC #3: Allowed imports permitted
# ---------------------------------------------------------------------------

class TestAllowedImports:
    def test_import_pandas_allowed(self):
        is_valid, errors = validate_code("import pandas as pd")
        assert is_valid is True, errors

    def test_import_numpy_allowed(self):
        is_valid, errors = validate_code("import numpy as np")
        assert is_valid is True, errors

    def test_import_matplotlib_allowed(self):
        is_valid, errors = validate_code("import matplotlib")
        assert is_valid is True, errors

    def test_import_matplotlib_pyplot_allowed(self):
        is_valid, errors = validate_code("import matplotlib.pyplot as plt")
        assert is_valid is True, errors

    def test_import_math_allowed(self):
        is_valid, errors = validate_code("import math")
        assert is_valid is True, errors

    def test_import_statistics_allowed(self):
        is_valid, errors = validate_code("import statistics")
        assert is_valid is True, errors

    def test_import_datetime_allowed(self):
        is_valid, errors = validate_code("import datetime")
        assert is_valid is True, errors

    def test_import_collections_allowed(self):
        is_valid, errors = validate_code("import collections")
        assert is_valid is True, errors

    def test_import_itertools_allowed(self):
        is_valid, errors = validate_code("import itertools")
        assert is_valid is True, errors

    def test_import_io_allowed(self):
        is_valid, errors = validate_code("import io")
        assert is_valid is True, errors

    def test_import_base64_allowed(self):
        is_valid, errors = validate_code("import base64")
        assert is_valid is True, errors

    def test_from_pandas_import_allowed(self):
        is_valid, errors = validate_code("from pandas import DataFrame")
        assert is_valid is True, errors

    def test_from_matplotlib_pyplot_import_allowed(self):
        is_valid, errors = validate_code("from matplotlib.pyplot import plot")
        assert is_valid is True, errors

    def test_from_matplotlib_import_pyplot_allowed(self):
        """Task 2.7: 'from matplotlib import pyplot as plt' form must be allowed."""
        is_valid, errors = validate_code("from matplotlib import pyplot as plt")
        assert is_valid is True, errors

    def test_from_pandas_import_star_allowed(self):
        is_valid, errors = validate_code("from pandas import *")
        assert is_valid is True, errors

    def test_from_io_import_bytesio_allowed(self):
        is_valid, errors = validate_code("from io import BytesIO")
        assert is_valid is True, errors

    def test_from_collections_import_defaultdict_allowed(self):
        is_valid, errors = validate_code("from collections import defaultdict")
        assert is_valid is True, errors


# ---------------------------------------------------------------------------
# AC #4: Blocked calls and patterns
# ---------------------------------------------------------------------------

class TestBlockedCalls:
    def test_eval_call_blocked(self):
        is_valid, errors = validate_code("result = eval('1 + 1')")
        assert is_valid is False
        assert any("eval" in e for e in errors)

    def test_exec_call_blocked(self):
        is_valid, errors = validate_code("exec('x = 1')")
        assert is_valid is False
        assert any("exec" in e for e in errors)

    def test_dunder_import_blocked(self):
        is_valid, errors = validate_code("mod = __import__('os')")
        assert is_valid is False
        assert any("__import__" in e for e in errors)

    def test_open_call_blocked(self):
        """open() is fully blocked — not just write modes (Story 3.2 code review update)."""
        is_valid, errors = validate_code("f = open('/etc/passwd', 'r')")
        assert is_valid is False
        assert any("open" in e for e in errors)

    def test_open_write_mode_blocked(self):
        is_valid, errors = validate_code("f = open('/tmp/out.txt', 'w')")
        assert is_valid is False
        assert any("open" in e for e in errors)


class TestBlockedNamespaceAccess:
    def test_os_attribute_call_blocked(self):
        """os.* attribute calls are blocked regardless of import."""
        is_valid, errors = validate_code("os.getcwd()")
        assert is_valid is False
        assert any("os" in e for e in errors)

    def test_os_attribute_access_without_call_blocked(self):
        """Assigning a blocked namespace attribute (no call) is also blocked.
        Prevents the f = os.system; f('ls') bypass pattern."""
        is_valid, errors = validate_code("f = os.system")
        assert is_valid is False
        assert any("os" in e for e in errors)

    def test_sys_exit_blocked(self):
        is_valid, errors = validate_code("sys.exit(0)")
        assert is_valid is False
        assert any("sys" in e for e in errors)

    def test_subprocess_run_blocked(self):
        is_valid, errors = validate_code("subprocess.run(['ls'])")
        assert is_valid is False
        assert any("subprocess" in e for e in errors)

    def test_socket_connect_blocked(self):
        is_valid, errors = validate_code("socket.connect(('example.com', 80))")
        assert is_valid is False
        assert any("socket" in e for e in errors)

    def test_urllib_request_blocked(self):
        is_valid, errors = validate_code("urllib.request.urlopen('http://example.com')")
        assert is_valid is False
        assert any("urllib" in e for e in errors)

    def test_requests_get_blocked(self):
        is_valid, errors = validate_code("requests.get('http://example.com')")
        assert is_valid is False
        assert any("requests" in e for e in errors)


# ---------------------------------------------------------------------------
# Multiple violations — all returned (not just first)
# ---------------------------------------------------------------------------

def test_multiple_violations_all_returned():
    code = "import os\nimport socket\neval('dangerous')"
    is_valid, errors = validate_code(code)
    assert is_valid is False
    assert len(errors) >= 3  # os import + socket import + eval call


def test_blocked_import_and_blocked_call_both_reported():
    code = "import sys\nexec('x = 1')"
    is_valid, errors = validate_code(code)
    assert is_valid is False
    assert len(errors) >= 2
    error_text = " ".join(errors)
    assert "sys" in error_text
    assert "exec" in error_text


# ---------------------------------------------------------------------------
# validate_code_node — LangGraph node wrapper
# ---------------------------------------------------------------------------

class TestValidateCodeNode:
    def test_valid_code_returns_empty_validation_errors(self):
        state = _make_state(generated_code="import pandas as pd\ndf = pd.read_csv(csv_path)")
        result = validate_code_node(state)
        assert "validation_errors" in result
        assert result["validation_errors"] == []

    def test_invalid_code_returns_execution_success_false(self):
        state = _make_state(generated_code="import os\nos.system('ls')")
        result = validate_code_node(state)
        assert result.get("execution_success") is False

    def test_invalid_code_returns_validation_errors_list(self):
        state = _make_state(generated_code="import os")
        result = validate_code_node(state)
        assert "validation_errors" in result
        assert len(result["validation_errors"]) >= 1

    def test_invalid_code_appends_translated_error_messages(self):
        state = _make_state(generated_code="import os")
        result = validate_code_node(state)
        assert "error_messages" in result
        assert len(result["error_messages"]) >= 1
        # Translated messages must not contain raw exception repr
        for msg in result["error_messages"]:
            assert "AllowlistViolationError" not in msg
            assert "Traceback" not in msg

    def test_syntax_error_produces_translated_message(self):
        state = _make_state(generated_code="def broken(:")
        result = validate_code_node(state)
        assert result.get("execution_success") is False
        assert "error_messages" in result
        # translate_error(SyntaxError) → "Generated code had a syntax error — retrying..."
        assert any("syntax error" in m.lower() for m in result["error_messages"])

    def test_allowlist_violation_produces_translated_message(self):
        state = _make_state(generated_code="import os")
        result = validate_code_node(state)
        # translate_error(AllowlistViolationError) → "Generated code used a restricted operation..."
        assert any("restricted operation" in m.lower() for m in result["error_messages"])

    def test_node_appends_to_existing_error_messages(self):
        """validate_code_node must append to, not replace, existing error_messages."""
        existing = ["Previous error from codegen."]
        state = _make_state(generated_code="import os", error_messages=existing)
        result = validate_code_node(state)
        assert len(result["error_messages"]) > 1
        assert existing[0] in result["error_messages"]

    def test_node_returns_only_changed_keys_on_success(self):
        """LangGraph convention: on success, only return keys that changed."""
        state = _make_state(generated_code="import pandas as pd")
        result = validate_code_node(state)
        # Should NOT include full state spread
        assert "user_query" not in result
        assert "csv_temp_path" not in result
        assert "intent" not in result

    def test_node_returns_only_changed_keys_on_failure(self):
        """LangGraph convention: on failure, only return keys that changed."""
        state = _make_state(generated_code="import os")
        result = validate_code_node(state)
        assert "user_query" not in result
        assert "csv_temp_path" not in result

    def test_empty_generated_code_is_valid(self):
        """Empty string should parse without errors."""
        state = _make_state(generated_code="")
        result = validate_code_node(state)
        assert result["validation_errors"] == []


# ---------------------------------------------------------------------------
# Module boundary guard: no streamlit import
# ---------------------------------------------------------------------------

def test_validator_no_streamlit_import():
    """Regression guard: pipeline/nodes/validator.py must never import streamlit."""
    src = (pathlib.Path(__file__).parent.parent / "pipeline" / "nodes" / "validator.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module] if node.module else []
            for name in names:
                assert "streamlit" not in (name or ""), \
                    f"streamlit must not be imported in validator.py — found: {name}"
