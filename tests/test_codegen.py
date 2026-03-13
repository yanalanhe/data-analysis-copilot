# tests/test_codegen.py
"""Unit tests for pipeline/nodes/codegen.py — generate_code() node."""
import ast
from unittest.mock import MagicMock, patch

import pipeline.nodes.codegen  # ensure module is in sys.modules before patching


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    """Return a minimal PipelineState-compatible dict for testing."""
    base = {
        "user_query": "plot sales over time",
        "csv_temp_paths": {"test.csv": "/tmp/test.csv"},
        "csv_metadata": "Available CSV files:\n- test.csv (100 rows): sales, date",
        "intent": "report",
        "plan": ["Load sales data", "Plot sales vs time", "Add trend line"],
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


def _make_mock_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.content = content
    return mock_response


# ---------------------------------------------------------------------------
# Task 2.1 — generate_code() returns {"generated_code": <non-empty str>} on success
# ---------------------------------------------------------------------------

def test_generate_code_returns_generated_code_key():
    """generate_code() must return a dict with non-empty 'generated_code' on success."""
    code = "import pandas as pd\ndf = pd.read_csv(csv_path)\nprint('done')"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert "generated_code" in result
    assert isinstance(result["generated_code"], str)
    assert result["generated_code"] != ""


def test_generate_code_strips_whitespace_from_response():
    """generate_code() strips leading/trailing whitespace from LLM response."""
    code = "  \nimport pandas as pd\n  "
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert result["generated_code"] == code.strip()


def test_generate_code_returns_only_generated_code_key_on_success():
    """On success, generate_code() returns ONLY the 'generated_code' key (LangGraph convention)."""
    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert set(result.keys()) == {"generated_code"}, (
        f"On success, generate_code must return only {{'generated_code'}}, got: {set(result.keys())}"
    )


# ---------------------------------------------------------------------------
# Task 2.2 — system prompt contains chart label requirements and CHART: format
# ---------------------------------------------------------------------------

def test_system_prompt_contains_plt_xlabel():
    """System prompt must require plt.xlabel for FR21."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "plt.xlabel" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must include plt.xlabel requirement (FR21)"
    )


def test_system_prompt_contains_plt_ylabel():
    """System prompt must require plt.ylabel for FR21."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "plt.ylabel" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must include plt.ylabel requirement (FR21)"
    )


def test_system_prompt_contains_plt_title():
    """System prompt must require plt.title for FR21."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "plt.title" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must include plt.title requirement (FR21)"
    )


def test_system_prompt_contains_plt_tight_layout():
    """System prompt must require plt.tight_layout for FR21."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "plt.tight_layout" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must include plt.tight_layout requirement (FR21)"
    )


def test_system_prompt_contains_chart_output_prefix():
    """System prompt must instruct CHART: prefix for subprocess chart output parsing."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "CHART:" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must include CHART: prefix instruction for chart output"
    )


def test_system_prompt_mentions_descriptive_labels():
    """System prompt must mention descriptive labels (not single letters)."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    prompt_lower = _CODEGEN_SYSTEM_PROMPT.lower()
    assert "descriptive" in prompt_lower, (
        "System prompt must mention 'descriptive' labels requirement (FR21)"
    )


def test_system_prompt_passed_as_system_message():
    """System prompt must be passed as SystemMessage (not HumanMessage)."""
    from langchain_core.messages import SystemMessage

    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state())

    messages = mock_llm.invoke.call_args[0][0]
    assert isinstance(messages[0], SystemMessage), (
        "First message must be a SystemMessage containing the system prompt"
    )
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert messages[0].content == _CODEGEN_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Task 2.3 — retry context included in user message when retry_count > 0
# ---------------------------------------------------------------------------

def test_retry_context_included_when_retry_count_gt_0():
    """When retry_count > 0 and error_messages non-empty, user message includes failure context."""
    from langchain_core.messages import HumanMessage

    code = "# corrected code"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(
            retry_count=1,
            error_messages=["Generated code had a syntax error — retrying with a corrected approach."]
        ))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    # Must contain something about the previous failure
    assert "syntax error" in human_msg.content or "Previous attempt" in human_msg.content, (
        "User message must include previous error context when retry_count > 0"
    )


def test_retry_context_not_included_when_retry_count_is_0():
    """When retry_count == 0, user message must NOT include 'Previous attempt' text."""
    from langchain_core.messages import HumanMessage

    code = "# first attempt"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(retry_count=0))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    assert "Previous attempt" not in human_msg.content, (
        "User message must NOT include retry context when retry_count == 0"
    )


def test_user_message_contains_plan_steps():
    """User message must include the execution plan steps."""
    from langchain_core.messages import HumanMessage

    plan = ["Load voltage data", "Calculate statistics", "Plot chart"]
    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(plan=plan))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    assert "Load voltage data" in human_msg.content
    assert "Calculate statistics" in human_msg.content
    assert "Plot chart" in human_msg.content


def test_user_message_contains_csv_filenames():
    """User message must include available CSV filenames for the generated code to use."""
    from langchain_core.messages import HumanMessage

    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(csv_temp_paths={"session_abc.csv": "/tmp/session_abc.csv"}))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    assert "session_abc.csv" in human_msg.content, (
        "User message must include the CSV filename so generated code can load data"
    )


def test_multiple_error_messages_uses_last_error_for_retry_context():
    """When multiple errors exist, only the last error is included in retry context."""
    from langchain_core.messages import HumanMessage

    errors = [
        "Generated code had a syntax error — retrying with a corrected approach.",
        "Generated code used a restricted operation — retrying with safer code.",
    ]
    code = "# fixed code"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(retry_count=2, error_messages=errors))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    # Last error should be present
    assert "restricted operation" in human_msg.content, (
        "Must include last error message in retry context"
    )


# ---------------------------------------------------------------------------
# Task 2.4 — error handling: LLM exception → translated message, not raw repr
# ---------------------------------------------------------------------------

def test_llm_error_returns_empty_code_and_translated_message():
    """On LLM exception, generate_code() returns empty code with translated error."""
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("connection refused xyz")
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())

    assert result["generated_code"] == "", "generated_code must be empty on error"
    assert "error_messages" in result
    assert len(result["error_messages"]) == 1


def test_llm_error_message_does_not_leak_raw_exception():
    """Error message must not contain raw exception text (no repr() or str() leakage)."""
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("secret internal detail xyz")
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())

    error_msg = result["error_messages"][0]
    assert "secret internal detail xyz" not in error_msg, (
        "Error message must not leak raw exception text"
    )
    assert "RuntimeError" not in error_msg, (
        "Error message must not contain exception class name"
    )


def test_llm_error_appends_to_existing_error_messages():
    """On LLM error, new translated message is appended to existing error_messages."""
    existing_errors = ["Generated code had a syntax error — retrying with a corrected approach."]
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("api failure")
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state(retry_count=1, error_messages=existing_errors))

    assert len(result["error_messages"]) == 2, (
        "New error must be appended to existing error_messages list"
    )
    assert result["error_messages"][0] == existing_errors[0]


def test_llm_error_returns_correct_keys():
    """On LLM exception, return dict must have 'generated_code' and 'error_messages' keys."""
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ValueError("bad response")
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())

    assert "generated_code" in result
    assert "error_messages" in result


# ---------------------------------------------------------------------------
# Task 2.5 — no streamlit import in pipeline/nodes/codegen.py
# ---------------------------------------------------------------------------

def test_no_streamlit_import_in_codegen():
    """Regression guard: pipeline/nodes/codegen.py must never import streamlit."""
    with open("pipeline/nodes/codegen.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "streamlit" not in alias.name, (
                        "pipeline/nodes/codegen.py must NOT import streamlit"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "streamlit" not in node.module, (
                        "pipeline/nodes/codegen.py must NOT import streamlit"
                    )


# ---------------------------------------------------------------------------
# Additional: uses gpt-4o model and correct LangChain message types
# ---------------------------------------------------------------------------

def test_generate_code_uses_gpt4o():
    """generate_code() must use ChatOpenAI with model='gpt-4o'."""
    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state())
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs.get("model") == "gpt-4o", (
        f"Expected model='gpt-4o', got: {call_kwargs.get('model')}"
    )


def test_generate_code_uses_temperature_zero():
    """generate_code() must use temperature=0 for deterministic code generation."""
    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state())
    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs.get("temperature") == 0, (
        f"Expected temperature=0, got: {call_kwargs.get('temperature')}"
    )


# ---------------------------------------------------------------------------
# Code review fixes — markdown fence stripping, Agg backend, edge cases
# ---------------------------------------------------------------------------

def test_strip_markdown_fences_python():
    """LLM response wrapped in ```python ... ``` must be stripped."""
    fenced = "```python\nimport pandas as pd\ndf = pd.read_csv(csv_path)\n```"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(fenced)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert not result["generated_code"].startswith("```"), (
        "Markdown fences must be stripped from generated code"
    )
    assert not result["generated_code"].endswith("```"), (
        "Closing markdown fence must be stripped"
    )
    assert "import pandas as pd" in result["generated_code"]


def test_strip_markdown_fences_bare():
    """LLM response wrapped in bare ``` ... ``` must be stripped."""
    fenced = "```\nimport pandas as pd\n```"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(fenced)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert not result["generated_code"].startswith("```")
    assert "import pandas as pd" in result["generated_code"]


def test_no_fences_code_unchanged():
    """Code without markdown fences must pass through unchanged."""
    clean = "import pandas as pd\ndf = pd.read_csv(csv_path)"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(clean)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        result = generate_code(_make_state())
    assert result["generated_code"] == clean


def test_system_prompt_contains_agg_backend():
    """System prompt must instruct matplotlib.use('Agg') for headless subprocess."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "matplotlib.use('Agg')" in _CODEGEN_SYSTEM_PROMPT or \
           'matplotlib.use("Agg")' in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must instruct Agg backend for headless execution"
    )


def test_system_prompt_contains_plt_close():
    """System prompt must instruct plt.close() to free memory after chart output."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    assert "plt.close()" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must instruct plt.close() after chart save"
    )


def test_csv_temp_paths_empty_omits_filenames_from_message():
    """When csv_temp_paths is empty, CSV filename info is omitted from user message."""
    from langchain_core.messages import HumanMessage

    code = "import pandas as pd"
    with patch("pipeline.nodes.codegen.ChatOpenAI") as mock_cls:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_mock_response(code)
        mock_cls.return_value = mock_llm
        from pipeline.nodes.codegen import generate_code
        generate_code(_make_state(csv_temp_paths={}, csv_metadata=""))

    messages = mock_llm.invoke.call_args[0][0]
    human_msg = messages[1]
    assert isinstance(human_msg, HumanMessage)
    assert "CSV files available" not in human_msg.content, (
        "When csv_temp_paths is empty, CSV filename info must be omitted"
    )


def test_system_prompt_blocks_open_entirely():
    """System prompt must block open() entirely, not just write modes."""
    from pipeline.nodes.codegen import _CODEGEN_SYSTEM_PROMPT
    # The prompt should say "open()" is blocked (without qualifying "with write modes")
    assert "open()" in _CODEGEN_SYSTEM_PROMPT, (
        "System prompt must block open() entirely per architecture AST allowlist"
    )
