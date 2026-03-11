# pipeline/nodes/codegen.py
"""Python code generation node.

NOTE: Never import streamlit in this file.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pipeline.state import PipelineState
from utils.error_translation import translate_error

_CODEGEN_SYSTEM_PROMPT = """You are a Python data analysis code generator.
Given an execution plan and a CSV file path, generate clean, executable Python code
that performs the analysis described in the plan.

Rules:
- Load data with pandas: df = pd.read_csv(csv_path)
- Use only these imports: pandas, numpy, matplotlib, matplotlib.pyplot, math, statistics,
  datetime, collections, itertools, io, base64
- Always set the matplotlib backend before importing pyplot:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
- For EVERY matplotlib chart, you MUST include ALL of the following with descriptive labels:
    plt.xlabel("Descriptive X Label (units)")  # e.g., "Time (ms)" not "t"
    plt.ylabel("Descriptive Y Label (units)")  # e.g., "Voltage (V)" not "v"
    plt.title("Chart Title describing what is shown")
    plt.tight_layout()
- After saving each chart, call plt.close() to free memory
- Output each chart as: print("CHART:" + base64.b64encode(buf.getvalue()).decode())
  where buf is a BytesIO containing the PNG bytes (use plt.savefig(buf, format='png', bbox_inches='tight'))
- Print any written analysis or trend summary as plain text to stdout (not prefixed with CHART:)
- Never use eval(), exec(), __import__(), open(), os.*, sys.*, subprocess.*
- The variable csv_path is available — use it directly to load the CSV
- Output ONLY the Python code, no markdown fences, no explanations"""


def _strip_markdown_fences(code: str) -> str:
    """Remove markdown code fences that LLMs sometimes add despite instructions."""
    if code.startswith("```"):
        # Remove opening fence (```python, ```py, or bare ```)
        code = code.split("\n", 1)[1] if "\n" in code else code[3:]
    if code.endswith("```"):
        code = code[:-3].rstrip()
    return code


def generate_code(state: PipelineState) -> dict:
    """Generate Python analysis code from the approved execution plan.

    Returns only changed keys per LangGraph convention.
    On retry (retry_count > 0), includes previous error context in the prompt.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    plan_text = "\n".join(
        f"{i + 1}. {step}" for i, step in enumerate(state.get("plan", []))
    )
    user_content = f"Execution plan:\n{plan_text}"
    if state.get("csv_temp_path"):
        user_content += f"\n\nCSV file path (use as csv_path variable): {state['csv_temp_path']}"
    if state.get("data_row_count") is not None:
        user_content += f"\nDataset row count: {state['data_row_count']}"

    # Retry context: include last error to guide a better attempt
    retry_count = state.get("retry_count", 0)
    if retry_count > 0:
        error_messages = state.get("error_messages", [])
        if error_messages:
            last_error = error_messages[-1]
            user_content += (
                f"\n\nPrevious attempt failed (attempt {retry_count}):\n{last_error}\n"
                "Please correct the issue and generate improved code."
            )

    messages = [
        SystemMessage(content=_CODEGEN_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    try:
        response = llm.invoke(messages)
        code = _strip_markdown_fences(response.content.strip())
        return {"generated_code": code}
    except Exception as e:
        error_msg = translate_error(e)
        existing_errors = list(state.get("error_messages", []))
        return {
            "generated_code": "",
            "error_messages": existing_errors + [error_msg],
        }
