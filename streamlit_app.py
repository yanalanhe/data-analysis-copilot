import os
import sys
import ast
import subprocess
import tempfile
import shutil
import streamlit as st
import pandas as pd
import time

from dotenv import load_dotenv
from typing import Literal
from typing_extensions import TypedDict
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langsmith.wrappers import wrap_openai
from langsmith import traceable, Client as LangSmithClient
from streamlit_ace import st_ace
from openai import OpenAI
from utils.error_translation import translate_error
from utils.reexec import build_reexec_state
from utils.templates import save_template, load_templates
from pipeline.graph import run_pipeline
from pipeline.nodes.validator import validate_code_node
from pipeline.nodes.executor import execute_code

load_dotenv()
ROW_HIGHT = 600
TEXTBOX_HIGHT = 90


def initialize_environment():
    load_dotenv()  # loads .env file — env vars (LANGCHAIN_TRACING_V2 etc) come from here only
    langsmith_client = None
    if os.getenv("LANGSMITH_API_KEY"):
        try:
            langsmith_client = LangSmithClient()
        except Exception:
            pass

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return (
        langsmith_client,
        openai_client,
        os.getenv("OPENAI_API_KEY"),
    )


langsmith_client, openai_client, OPENAI_API_KEY = initialize_environment()
if langsmith_client is not None:
    try:
        openai_client = wrap_openai(openai_client)
    except Exception:
        pass

# Initialize new-pipeline session state keys (idempotent — runs every rerun)
from utils.session import init_session_state
init_session_state()

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o"


# ─────────────────────────────────────────────
# Shared utility helpers
# ─────────────────────────────────────────────

def get_stream(sentence):
    for word in sentence.split():
        yield word + " "
        time.sleep(0.05)


def get_data(placeholder):
    new_data = st.session_state.df.to_csv()
    return new_data


def get_dataframe():
    df = pd.DataFrame(
        {
            "A": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "B": [15, 25, 35, 45, 55, 65, 75, 85, 95, 105],
            "C": [5, 15, 25, 35, 45, 55, 65, 75, 85, 95],
        }
    )
    return df


def handle_table_change():
    if "table_changed" in st.session_state and st.session_state["table_changed"]:
        st.session_state["chat_history"].append(
            {"role": "bot", "content": "A change was made to the table."}
        )


def _combine_uploaded_dfs(uploaded_dfs: dict) -> pd.DataFrame:
    """Combine uploaded DataFrames into a single DataFrame.

    Single-file: returns the DataFrame directly.
    Multi-file: concatenates with ignore_index=True.
    """
    if len(uploaded_dfs) == 1:
        return list(uploaded_dfs.values())[0]
    return pd.concat(list(uploaded_dfs.values()), ignore_index=True)


def _on_csv_upload(uploaded_files) -> None:
    """Handle CSV file upload: populate uploaded_dfs, write per-file temp files, update df.

    Stores each file as a DataFrame in st.session_state["uploaded_dfs"] keyed by filename.
    Writes one temp CSV per file and sets st.session_state["csv_temp_paths"] as a dict.
    Updates st.session_state.df to first file for backward compat with run_tests() and existing pipeline.
    Calls detect_large_data() and stores result in session state (Story 4.1).
    Skips re-processing if the uploaded file set has not changed since last call.
    """
    from utils.large_data import detect_large_data

    # Skip re-processing if the same files are still in the uploader (rerun guard)
    upload_signature = tuple(sorted((f.name, f.size) for f in uploaded_files))
    if st.session_state.get("_upload_signature") == upload_signature:
        return
    st.session_state["_upload_signature"] = upload_signature

    # Story 4.2: Reset recovery state when new files are uploaded
    st.session_state["recovery_applied"] = ""

    # Load each uploaded file into a DataFrame
    new_dfs = {}
    for f in uploaded_files:
        try:
            new_dfs[f.name] = pd.read_csv(f)
        except Exception as e:
            st.error(f"Failed to read **{f.name}**: {translate_error(e)}")
            continue

    if not new_dfs:
        return

    st.session_state["uploaded_dfs"] = new_dfs

    # Keep st.session_state.df as first file for backward compat
    first_df = list(new_dfs.values())[0]
    st.session_state.df = first_df

    # Clean up previous temp paths if they exist
    old_paths = st.session_state.get("csv_temp_paths", {})
    for old_path in old_paths.values():
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass  # Safe to ignore — temp file may already be gone

    # Write one temp file per uploaded DataFrame
    new_temp_paths = {}
    for name, df in new_dfs.items():
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", encoding="utf-8"
        ) as tmp:
            df.to_csv(tmp, index=False)
            new_temp_paths[name] = tmp.name

    st.session_state["csv_temp_paths"] = new_temp_paths

    # Large data detection — runs on upload before any pipeline execution (NFR5, Story 4.1)
    combined_size_mb = sum(f.size for f in uploaded_files) / 1_048_576
    total_rows = sum(len(df) for df in new_dfs.values())
    is_large = detect_large_data(total_rows, combined_size_mb)
    if is_large:
        st.session_state["large_data_detected"] = True
        file_count = len(new_dfs)
        st.session_state["large_data_message"] = (
            f"Your dataset has {total_rows:,} rows across {file_count} files / {combined_size_mb:.1f} MB, "
            "which exceeds the visualization threshold."
        )
    else:
        st.session_state["large_data_detected"] = False
        st.session_state["large_data_message"] = ""


# ─────────────────────────────────────────────
# Story 4.2: Auto-downsample helper
# ─────────────────────────────────────────────

def _apply_downsample() -> None:
    """Apply uniform stride downsampling to each uploaded file independently.

    Overwrites each temp CSV with its downsampled data.
    Sets recovery_applied = "downsampled" in session state.
    Called from the auto-downsample button in _execution_panel().
    """
    from utils.large_data import apply_uniform_stride

    uploaded_dfs = st.session_state.get("uploaded_dfs", {})
    csv_temp_paths = st.session_state.get("csv_temp_paths", {})
    if not uploaded_dfs:
        st.warning("No uploaded dataset found. Please upload a CSV file first.")
        return

    # Downsample each file independently and overwrite its temp file
    new_temp_paths = {}
    for name, df in uploaded_dfs.items():
        downsampled_df = apply_uniform_stride(df)

        # Overwrite existing temp file if present
        if name in csv_temp_paths and csv_temp_paths[name]:
            temp_path = csv_temp_paths[name]
            if os.path.exists(temp_path):
                downsampled_df.to_csv(temp_path, index=False)
                new_temp_paths[name] = temp_path
            else:
                # Temp file is gone; create a new one
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv", mode="w", encoding="utf-8"
                ) as tmp:
                    downsampled_df.to_csv(tmp, index=False)
                    new_temp_paths[name] = tmp.name
        else:
            # No temp file for this one yet; create one
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv", mode="w", encoding="utf-8"
            ) as tmp:
                downsampled_df.to_csv(tmp, index=False)
                new_temp_paths[name] = tmp.name

    st.session_state["csv_temp_paths"] = new_temp_paths

    # Update df in session to first downsampled file for backward compat with existing pipeline
    first_name = list(uploaded_dfs.keys())[0]
    st.session_state.df = apply_uniform_stride(uploaded_dfs[first_name])
    st.session_state["recovery_applied"] = "downsampled"


# ─────────────────────────────────────────────
# New pipeline chat helpers (Story 2.1)
# ─────────────────────────────────────────────

def _make_initial_pipeline_state(user_input: str) -> dict:
    """Build a complete PipelineState dict with all 18 fields.

    Builds csv_metadata string from uploaded_dfs for LLM context.
    """
    uploaded_dfs = st.session_state.get("uploaded_dfs", {})
    csv_temp_paths = st.session_state.get("csv_temp_paths", {})

    # Build csv_metadata string for LLM context
    metadata_lines = []
    for name, df in uploaded_dfs.items():
        cols = ", ".join(df.columns.tolist())
        metadata_lines.append(f"- {name} ({len(df)} rows): {cols}")
    csv_metadata = (
        "Available CSV files:\n" + "\n".join(metadata_lines)
        if metadata_lines
        else ""
    )

    return {
        "user_query": user_input,
        "csv_temp_paths": csv_temp_paths,
        "csv_metadata": csv_metadata,
        "intent": "chat",
        "plan": [],
        "generated_code": "",
        "validation_errors": [],
        "execution_output": "",
        "execution_success": False,
        "retry_count": 0,
        "replan_triggered": False,
        "error_messages": [],
        "report_charts": [],
        "report_text": "",
        "large_data_detected": bool(st.session_state.get("large_data_detected", False)),
        "large_data_message": st.session_state.get("large_data_message", ""),
        "recovery_applied": st.session_state.get("recovery_applied", ""),
    }


def _generate_qa_response(user_input: str) -> str:
    """Call LLM with dataset context to answer a factual question about the data."""
    try:
        df = st.session_state["df"] if "df" in st.session_state else None
        if df is not None:
            # Limit columns shown to LLM to avoid oversized prompts on wide datasets
            cols = list(df.columns)
            preview_cols = cols[:30] if len(cols) > 30 else cols
            context = (
                f"Dataset shape: {df.shape}\n"
                f"Columns: {cols}\n"
                f"Sample (first 3 rows, up to 30 columns):\n"
                f"{df[preview_cols].head(3).to_string()}"
            )
        else:
            context = "No dataset loaded."
        response = openai_client.chat.completions.create(
            model=st.session_state.get("openai_model", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data analysis assistant. Answer the user's question "
                        "about their dataset using the context below.\n\n" + context
                    ),
                },
                {"role": "user", "content": user_input},
            ],
        )
        return response.choices[0].message.content
    except Exception:
        return "I'm unable to respond right now. Please check your connection and try again."


def _generate_chat_response(user_input: str) -> str:
    """Call LLM to respond to general conversation, including chat history for context."""
    try:
        # Build message list from chat_history for multi-turn context
        history_messages = []
        for msg in st.session_state.get("chat_history", []):
            role = "assistant" if msg["role"] == "bot" else msg["role"]
            history_messages.append({"role": role, "content": msg["content"]})

        response = openai_client.chat.completions.create(
            model=st.session_state.get("openai_model", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data analysis copilot. You help users analyze data, "
                        "create charts and reports, and answer questions about their datasets. "
                        "You can upload CSV files, classify analysis intent, and generate "
                        "execution plans. Respond conversationally and helpfully."
                    ),
                },
            ]
            + history_messages
            + [{"role": "user", "content": user_input}],
        )
        return response.choices[0].message.content
    except Exception:
        return "I'm unable to respond right now. Please check your connection and try again."


def _handle_chat_input(user_input: str) -> None:
    """Orchestrate intent classification and route to appropriate response handler."""
    # Reset execution approval state for each new query cycle (Story 2.3 — AC #3)
    st.session_state["plan_approved"] = False
    st.session_state["pipeline_running"] = False

    from pipeline.nodes.intent import classify_intent

    pipeline_state = _make_initial_pipeline_state(user_input)

    try:
        intent_result = classify_intent(pipeline_state)
        intent = intent_result.get("intent", "chat")
    except Exception:
        intent = "chat"

    pipeline_state = {**pipeline_state, "intent": intent}
    st.session_state["pipeline_state"] = pipeline_state

    if intent == "report":
        from pipeline.nodes.planner import generate_plan
        plan_result = generate_plan(pipeline_state)
        pipeline_state = {**pipeline_state, **plan_result}
        st.session_state["pipeline_state"] = pipeline_state
        bot_msg = (
            "I've created an execution plan for your request. "
            "Check the Plan tab to review it."
        )
        st.session_state["chat_history"].append({"role": "bot", "content": bot_msg})
    elif intent == "qa":
        answer = _generate_qa_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": answer})
    else:  # "chat"
        response = _generate_chat_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": response})


# ─────────────────────────────────────────────
# LangGraph State
# ─────────────────────────────────────────────

class CodePlanState(TypedDict):
    messages: list      # conversation messages, first entry is the user task
    plan: list          # remaining plan steps (strings), consumed step by step
    code_files: dict    # accumulated per-step code files {filename: code}
    test_results: dict  # result from last subprocess run
    errors: list        # errors from last failed run
    iterations: int     # rewrite attempts for the current step
    step_count: int     # total steps successfully completed


MAX_CODE_RETRIES = 3
MAX_PLAN_RETRIES = 2


# ─────────────────────────────────────────────
# Subprocess-based code runner
# ─────────────────────────────────────────────

def run_tests(code_files: dict) -> dict:
    """Execute the latest generated code file in a temp directory."""
    if not code_files:
        return {"passed": False, "errors": ["No code files to run"]}
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            st.session_state.df.to_csv(os.path.join(tmpdir, "data.csv"), index=False)

            for filename, code in code_files.items():
                full_code = (
                    "import pandas as pd\n"
                    "import matplotlib\nmatplotlib.use('Agg')\n"
                    "import matplotlib.pyplot as plt\n"
                    "import numpy as np\n"
                    "df = pd.read_csv('data.csv')\n\n"
                    + code
                )
                with open(os.path.join(tmpdir, filename), "w") as f:
                    f.write(full_code)

            latest_file = list(code_files.keys())[-1]
            result = subprocess.run(
                [sys.executable, latest_file],
                cwd=tmpdir, capture_output=True, text=True, timeout=30,
            )

            # Copy *.png to workspace if it was generated
            for fname in os.listdir(tmpdir):
                if fname.endswith(".png"):
                    shutil.copy(os.path.join(tmpdir, fname), os.path.join(os.getcwd(), fname))
                    passed = result.returncode == 0
            if not passed:
                print(f"[LG] STDERR: {result.stderr}")
                print(f"[LG] STDOUT: {result.stdout}")
            return {
                "passed": passed,
                "errors": [result.stderr] if not passed else [],
                "stdout": result.stdout,
            }
    except subprocess.TimeoutExpired:
        return {"passed": False, "errors": ["Code execution timed out"]}
    except Exception as e:
        return {"passed": False, "errors": [str(e)]}


# ─────────────────────────────────────────────
# LangGraph nodes
# ─────────────────────────────────────────────

def lg_plan_node(state: CodePlanState) -> Command[Literal["write_code"]]:
    print(f"\n[LG] Entering lg_plan_node (step_count: {state.get('step_count', 0)})")
    task = state["messages"][-1]["content"]
    data_csv = st.session_state.df.to_csv()

    prompt = (
        task
        + """ \n make a simple plan that is simple to understand without technical terms to create code in python 
            to analyze this data(do not include the code), only include the plan as list of steps in the output. 
            At the same time, you are also given a list of tools, they are python_repl_tool for writing code, and another one is called web_search for searching on the web for knowledge you do not know. 
            Please assign the right tool to do each step, knowing the tools that got activated later will know the output of the previous tools. 
            the plan can be hierarchical, meaning that when multiple related and consecutive step can be grouped in one big step and be achieve by the same tool,
            you can group under a parent step and have them as sub-steps and only mention the tool recommended for the partent step. try to limit your parent step to be less than 5 steps. 
            At the each parent step of the plan, please indicate the tool you recommend in a [] such as [Tool: web_search], and put it at the begining of that step. Do not indicate the tool recommendation for sub-steps
            In your output please only give one coherent plan with no analysis
                """
        + "\n this is the data \n"
        + data_csv
    )

    # If replanning due to repeated failures, add context
    if state.get("errors"):
        prompt += (
            f"\n\nNote: A previous plan was attempted but kept failing with:\n"
            f"{chr(10).join(state['errors'])}\n"
            "Please revise the plan to avoid these issues."
        )

    response = openai_client.chat.completions.create(
        model=st.session_state["openai_model"],
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()
    steps = [line.strip("- •").strip() for line in raw.splitlines() if line.strip()]

    return Command(update={"plan": steps, "iterations": 0}, goto="write_code")


def lg_write_code(state: CodePlanState) -> Command[Literal["check_code"]]:
    print(f"\n[LG] Entering lg_write_code (step_count: {state.get('step_count', 0)})")
    all_steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(state["plan"]))
    print(f"[LG] Writing code for all {len(state['plan'])} steps at once")
    data_csv = st.session_state.df.to_csv()

    response = openai_client.chat.completions.create(
        model=st.session_state["openai_model"],
        temperature=0,
        messages=[{
            "role": "user",
            "content": (
                f"Write a single complete Python script to execute ALL of these steps:\n{all_steps}\n\n"
                "Assume these are already available: `df` (pandas DataFrame), pd, plt, np.\n"
                f"Full dataset:\n{data_csv}\n\n"
                "Instructions:\n"
                "  - Write one complete Python script covering all steps\n"
                "  - Use print() to output results with descriptive labels\n"
                "  - Save plots as 'plot.png' with plt.savefig('plot.png')\n"
                "  - Do not redefine df or re-import libraries\n"
                "  - Return ONLY plain Python code without markdown or code fences"
            ),
        }],
    )

    code = response.choices[0].message.content.strip()
    if code.startswith("```"):
        code = "\n".join(code.splitlines()[1:])
    if code.endswith("```"):
        code = "\n".join(code.splitlines()[:-1])

    return Command(update={"code_files": {"analysis.py": code}}, goto="check_code")


def lg_check_code(state: CodePlanState) -> Command[Literal["rewrite_code", END]]:
    print(f"\n[LG] Entering lg_check_code (step_count: {state.get('step_count', 0)})")

    code = state["code_files"]["analysis.py"]

    # ── Static checks (free — no LLM call) ──

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return Command(
            update={"errors": [f"SyntaxError: {e}"], "test_results": {"passed": False}},
            goto="rewrite_code",
        )

    # Forbidden library check
    forbidden = ["requests", "flask", "django", "sklearn", "tensorflow", "torch", "scipy"]
    for lib in forbidden:
        if f"import {lib}" in code or f"from {lib}" in code:
            return Command(
                update={"errors": [f"Forbidden library: {lib}"], "test_results": {"passed": False}},
                goto="rewrite_code",
            )

    # ── LLM logic review — only on first attempt (iterations == 0) ──
    if state.get("iterations", 0) == 0:
        review_response = openai_client.chat.completions.create(
            model=st.session_state["openai_model"],
            temperature=0,
            messages=[{
                "role": "user",
                "content": (
                    f"Review this Python code for correctness.\n"
                    f"It is meant to: {state['messages'][-1]['content']}\n\n"
                    f"CODE:\n{code}\n\n"
                    "If correct and complete, respond with exactly: OK\n"
                    "If there is a logical bug or missing step, respond with ONE sentence describing the issue only. Do not rewrite the code."
                ),
            }],
        )
        review = review_response.choices[0].message.content.strip()
        if review.upper() != "OK":
            return Command(
                update={"errors": [f"Logic issue: {review}"], "test_results": {"passed": False}},
                goto="rewrite_code",
            )

    # ── Subprocess execution check ──
    print(f"[LG] Running tests on analysis.py...")
    test_results = run_tests(state["code_files"])
    print(f"[LG] Test result: {'PASSED' if test_results['passed'] else 'FAILED'}")

    if test_results["passed"]:
        return Command(update={"step_count": 1}, goto=END)
    else:
        return Command(
            update={"errors": test_results["errors"], "test_results": test_results},
            goto="rewrite_code",
        )

def lg_rewrite_code(state: CodePlanState) -> Command[Literal["check_code", "update_plan"]]:
    print(f"\n[LG] Entering lg_rewrite_code (step_count: {state.get('step_count', 0)}, iterations: {state['iterations']})")

    if state["iterations"] >= MAX_CODE_RETRIES:
        print(f"[LG] Max iterations ({MAX_CODE_RETRIES}) reached, moving to update_plan")
        return Command(update={"step_count": state.get("step_count", 0)}, goto="update_plan")

    print(f"[LG] Attempt {state['iterations'] + 1} to fix code...")

    broken_code = state["code_files"]["analysis.py"]
    errors = "\n".join(state["errors"])

    response = openai_client.chat.completions.create(
        model=st.session_state["openai_model"],
        temperature=0,
        messages=[{
            "role": "user",
            "content": (
                f"Fix this Python code that failed:\n\n"
                f"Code:\n{broken_code}\n\n"
                f"Errors:\n{errors}\n\n"
                "The DataFrame `df` is already loaded. Return ONLY fixed Python code without markdown."
            ),
        }],
    )

    fixed_code = response.choices[0].message.content.strip()
    if fixed_code.startswith("```"):
        fixed_code = "\n".join(fixed_code.splitlines()[1:])
    if fixed_code.endswith("```"):
        fixed_code = "\n".join(fixed_code.splitlines()[:-1])

    updated_files = {"analysis.py": fixed_code}
    return Command(
        update={"code_files": updated_files, "iterations": state["iterations"] + 1},
        goto="check_code",
    )


def lg_update_plan(state: CodePlanState) -> Command[Literal["write_code", END]]:
    print(f"\n[LG] Entering lg_update_plan (step_count: {state.get('step_count', 0)})")

    errors = "\n".join(state["errors"])
    remaining = "\n".join(state["plan"])

    response = openai_client.chat.completions.create(
        model=st.session_state["openai_model"],
        temperature=0,
        messages=[{
            "role": "user",
            "content": (
                f"The plan keeps failing with these errors:\n{errors}\n\n"
                f"Remaining steps:\n{remaining}\n\n"
                "Revise the steps to avoid these errors. "
                "Return ONLY a Python list of strings. No explanation, no markdown."
            ),
        }],
    )

    raw = response.choices[0].message.content.strip()
    try:
        new_steps = ast.literal_eval(raw)
        if not isinstance(new_steps, list):
            new_steps = [raw]
    except Exception:
        new_steps = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]

    if not new_steps:
        return Command(goto=END)
    return Command(update={"plan": new_steps, "iterations": 0}, goto="write_code")


# ─────────────────────────────────────────────
# Build and compile the LangGraph
# ─────────────────────────────────────────────

_graph = StateGraph(CodePlanState)
_graph.add_node("planner", lg_plan_node)
_graph.add_node("write_code", lg_write_code)
_graph.add_node("check_code", lg_check_code)
_graph.add_node("rewrite_code", lg_rewrite_code)
_graph.add_node("update_plan", lg_update_plan)
_graph.set_entry_point("planner")
langgraph_app = _graph.compile()


def _print_langgraph_structure(graph):
    try:
        graph_view = graph.get_graph()
        if hasattr(graph_view, "draw_ascii"):
            print("\n" + "=" * 50)
            print("LangGraph structure:")
            print("=" * 50 + "\n" + graph_view.draw_ascii())
            print("=" * 50 + "\n")
            return
        print(f"LangGraph nodes: {list(getattr(graph_view, 'nodes', []))}")
        print(f"LangGraph edges: {list(getattr(graph_view, 'edges', []))}")
    except Exception as exc:
        print(f"LangGraph structure unavailable: {exc}")


if "langgraph_initialized" not in st.session_state:
    _print_langgraph_structure(langgraph_app)
    st.session_state.langgraph_initialized = True


# ─────────────────────────────────────────────
# generate_code_for_display_report
# ─────────────────────────────────────────────

def generate_code_for_display_report(execution_agent_response):
    st.session_state.agent_thoughtflow = (
        "Here is the final output: "
        + str(execution_agent_response["output"])
        + "\nHere is the log of the different step's output, you will be able to find the useful information within there: \n"
        + "".join(
            str(step.log) for step in execution_agent_response["intermediate_steps"]
        )
    )

    code_with_display = openai_client.chat.completions.create(
        model=st.session_state["openai_model"],
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": """You are creating a report for the user's question: """
                + st.session_state.current_user_input
                + """use st.write or st.image to display the result of the given thoughtflow of an agent that already did all the calculation needed to answer the question: \n\n\n------------------------\n"""
                + st.session_state.agent_thoughtflow
                + """
\n\n\n------------------------\nNote that all the results are already in the thoughtflow, you just need to print them out rather than trying to recalculate them.
Only use st.write(), st.image(), st.metric() and Streamlit functions to display. Do not reference df or variables directly.
Only respond with code as plain text without code block syntax around it. Again, do not write code to do any calculation. you are only here to print the results from the above thought flow""",
            }
        ],
    )

    return code_with_display


# ─────────────────────────────────────────────
# execute_plan
# ─────────────────────────────────────────────

def execute_plan(plan):
    print("[PLAN EXECUTION STARTED]")
    status_container = st.empty()

    steps = [line.strip("- •").strip() for line in plan.splitlines() if line.strip()]
    print(f"[PLAN] Total steps to execute: {len(steps)}")
    for i, step in enumerate(steps, 1):
        print(f"[PLAN] {i}. {step}")

    initial_state: CodePlanState = {
        "messages": [
            {"role": "user", "content": st.session_state.get("current_user_input", plan)}
        ],
        "plan": steps,
        "code_files": {},
        "test_results": {},
        "errors": [],
        "iterations": 0,
        "step_count": 0,
    }

    final_code_files = {}

    for step_output in langgraph_app.stream(initial_state, config={"recursion_limit": 500}):
        node_name = list(step_output.keys())[0]
        node_data = step_output[node_name] or {}


        if node_data.get("code_files"):
            final_code_files = node_data["code_files"]

    status_container.success("✅ Done!")
    formatted_output = ""

    if final_code_files:
        code_block = "\n\n".join(
            f"```python\n# --- {fname} ---\n{code}\n```"
            for fname, code in final_code_files.items()
        )
        formatted_output = f"### Final Generated Code\n\n{code_block}"

    st.session_state.formatted_output = formatted_output

    if final_code_files:
        print(f"\n[RESULTS] Generated {len(final_code_files)} code file(s)")
        all_code = "\n\n".join(
            f"# --- {fname} ---\n{code}" for fname, code in final_code_files.items()
        )

        # Collect stdout from all steps for the thoughtflow
        all_stdout = ""
        for filename, code in final_code_files.items():
            result = run_tests({filename: code})
            all_stdout += f"\n# {filename} output:\n{result.get('stdout', '')}"

        # Build response object matching generate_code_for_display_report interface
        langgraph_response = {
            "output": f"Successfully executed {len(final_code_files)} code files",
            "intermediate_steps": [
                type("Step", (), {
                    "tool": "langgraph_executor",
                    "tool_input": all_code,
                    "log": "LangGraph executed and tested the following code:\n" + all_code + "\n\nOutput:\n" + all_stdout,
                })()
            ],
        }

        code_for_displaying_report = generate_code_for_display_report(langgraph_response)
        st.session_state.code = code_for_displaying_report.choices[0].message.content

    st.session_state.messages.append(
        {"role": "assistant", "content": "Report generated! Check the Report panel below."}
    )

    print(f"\n{'=' * 60}")
    print("[PLAN EXECUTION COMPLETED]")
    print(f"{'=' * 60}\n")

    st.rerun()


# ─────────────────────────────────────────────
# Chatbot response
# ─────────────────────────────────────────────

@traceable(name="generate_chatbot_reponse")
def generate_chatbot_response(openai_client, session_state, user_input):
    stream = openai_client.chat.completions.create(
        model=session_state["openai_model"],
        messages=[
            {
                "role": "system",
                "content": """You are a data analysis Copilot that is able to help user to generate report with data analysis in them. you are able to search on internet and you're able to help people to look into the table data from the user. however currently you can only do those if user is sending you a message stating clearly that they like to create a report. if they are not asking you about creating a report please try to answer their questions and explain what you can do to help, and ask them to create a report if that's their goal if you think it is needed, 
                   for example, create a report of column B and column C and caluclate the correlation between the two columns""",
            }
        ]
        + [{"role": m["role"], "content": m["content"]} for m in session_state.messages],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "trigger_report_generation",
                    "description": "Trigger this function when user asks about creating a report or any calculation to do with the existing dataset",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_message": {
                                "type": "string",
                                "description": "The user's message asking about creating a report or any calculation to do with the existing dataset",
                            }
                        },
                        "required": ["user_message"],
                    },
                },
            }
        ],
        tool_choice="auto",
    )

    response_message = stream.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls and tool_calls[0].function.name == "trigger_report_generation":
        st.write_stream(
            get_stream("Got it, here is a plan to create report for this request of yours:")
        )
        result = get_data(session_state.df)
        session_state.current_user_input = user_input

        plan = openai_client.chat.completions.create(
            model=session_state["openai_model"],
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": user_input
                    + """ \n make a simple plan that is simple to understand without technical terms to create code in python 
                        to analyze this data(do not include the code), only include the plan as list of steps in the output. 
                        At the same time, you are also given a list of tools, they are python_repl_tool for writing code, and another one is called web_search for searching on the web for knowledge you do not know. 
                        Please assign the right tool to do each step, knowing the tools that got activated later will know the output of the previous tools. 
                        the plan can be hierarchical, meaning that when multiple related and consecutive step can be grouped in one big step and be achieve by the same tool,
                        you can group under a parent step and have them as sub-steps and only mention the tool recommended for the partent step. try to limit your parent step to be less than 5 steps. 
                        At the each parent step of the plan, please indicate the tool you recommend in a [] such as [Tool: web_search], and put it at the begining of that step. Do not indicate the tool recommendation for sub-steps
                        In your output please only give one coherent plan with no analysis
                            """
                    + "\n this is the data \n"
                    + result,
                }
            ],
            stream=True,
        )
        response = st.write_stream(plan)
        st.write_stream(
            get_stream(
                "📝 If you like the plan, please click on 'Execute Plan' button on the 'Plan' tab in the top right panel. Or feel free to ask me to revise the plan in this chat"
            )
        )
        session_state.plan = response
    else:
        response = st.write_stream(get_stream(stream.choices[0].message.content))

    return response


# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────

if "plan" not in st.session_state:
    st.session_state.plan = ""
if "code" not in st.session_state:
    st.session_state.code = """
st.write("There is no report created yet, please ask the chatbot to create a report if you need")
"""
if "thoughtflow" not in st.session_state:
    st.session_state.agent_thoughtflow = ""
if "current_user_input" not in st.session_state:
    st.session_state.current_user_input = ""


class SessionStateAutoClass:
    def __setattr__(self, name, value):
        if getattr(self, name, None) != value:
            st.session_state[name] = value
            st.rerun()

    def __getattr__(self, name):
        return st.session_state.get(name, None)


session_state_auto = SessionStateAutoClass()

if "formatted_output" not in st.session_state:
    st.session_state.formatted_output = ""
session_state_auto.formatted_output = st.session_state.formatted_output


# ─────────────────────────────────────────────
# Execution panel (Story 3.6)
# ─────────────────────────────────────────────

@st.fragment
def _execution_panel() -> None:
    """Non-blocking execution panel decorated with @st.fragment.

    @st.fragment isolates reruns to this panel only — the chat panel and tabs
    remain interactive during pipeline execution (NFR4).

    Behaviour:
    - When pipeline_running is True: runs run_pipeline(), shows st.status progress,
      stores result in session_state, resets pipeline_running.
    - Always renders the current report output (charts + text) or a placeholder.
    """
    st.write("### AI Generated Report")

    # Story 4.1 + 4.2: Inline large data warning with recovery options (no modal, FR27, FR28)
    large_data = st.session_state.get("large_data_detected", False)
    recovery = st.session_state.get("recovery_applied", "")

    if large_data:
        base_msg = st.session_state.get("large_data_message", "")
        filter_hint = " You can also filter your data in the editable data table before running analysis."
        st.warning(base_msg + filter_hint)

        if recovery != "downsampled":
            # Story 4.2: Show auto-downsample button (AC #1)
            if st.button("Auto-downsample to 10,000 points"):
                _apply_downsample()
                st.rerun()
        else:
            # Story 4.2: Recovery confirmation note (AC #4)
            st.success("Downsampled to 10,000 points using uniform stride.")

    ps = st.session_state.get("pipeline_state")

    if st.session_state.get("pipeline_running"):
        initial_state = ps
        if initial_state is None:
            st.warning("No pipeline state found. Please submit a query first.")
            st.session_state["pipeline_running"] = False
            return

        with st.status("Running analysis...", expanded=True) as status:
            status.update(label="⏳ Classifying intent → Generating plan → Validating code → Executing → Rendering report")
            try:
                result = run_pipeline(initial_state)
            except Exception as e:
                from utils.error_translation import translate_error
                status.update(label="❌ Pipeline error", state="error")
                result = {
                    **initial_state,
                    "execution_success": False,
                    "error_messages": list(initial_state.get("error_messages", [])) + [translate_error(e)],
                }
            else:
                status.update(label="✅ Analysis complete!", state="complete")

        st.session_state["pipeline_state"] = result
        st.session_state["pipeline_running"] = False
        ps = result
        st.rerun()  # Full rerun so tabs get updated pipeline_state with generated_code

    # Render report output
    if ps and ps.get("execution_success"):
        charts = ps.get("report_charts") or []
        for chart_bytes in charts:
            st.image(chart_bytes)
        report_text = ps.get("report_text", "")
        if report_text:
            st.markdown(report_text)
        if not charts and not report_text:
            st.info("Analysis complete. No chart output was produced.")
    elif ps and ps.get("error_messages"):
        for msg in ps["error_messages"]:
            st.error(msg)
    elif ps and ps.get("execution_success") is False and ps.get("generated_code"):
        st.warning("The analysis did not complete successfully. Please try again or modify your request.")
    else:
        st.info("Run an analysis to see results here.")

    # Story 4.2 AC #6: warn if pipeline ran on full large dataset without recovery
    if large_data and recovery == "" and ps and (ps.get("error_messages") or ps.get("execution_success") is False):
        st.warning(
            "Analysis ran on the full large dataset. Results may be incomplete or unrenderable. "
            "Consider using the auto-downsample button above."
        )


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.set_page_config(layout="wide")

# Title and Welcome Section
st.title("🔌 Circuit Board Data Analysis Tool")

# Usage Section
with st.expander("📖 Usage Examples", expanded=False):
    st.warning("⚠️ **Important:** You must upload the related CSV files to the 'User Data Set' section before using these examples.")
    st.markdown("""
    **1. Diagnose Machine Event (3-Step Analysis)**
    ```
    Diagnose one machine event using three synchronized CSVs from the same time window.
    In CSV1("chart1_tracking_command_response.csv"), compare Command(command_pct) vs Response(response_pct).
    If Response deviates >±5% during transitions, flag tracking failure.
    If tracking fails, check CSV2(chart2_power_supply_output.csv): compare Supply Voltage(supply_v) vs Output(output_rpm);
    If Output weakens, drops, or gets noisy when Voltage dips, classify power-related failure.
    If not, check CSV3(chart3_mode_sensor_mismatch.csv): compare Sensor1(sensor2_pct) vs Sensor2(sensor2_pct);
    If they diverge mainly in one mode/event window, classify mode-specific sensor mismatch.
    Output format: Step 1 finding; Step 2 finding; Step 3 finding; Final fault type;
    Root-cause hypothesis;
    Recommended next check.
    Include three charts in the output report: one for each step (CSV1, CSV2, CSV3).
    ```

    **2. Analyze Command vs Response Tracking**
    ```
    Analyze uploaded "chart1_tracking_command_response.csv".
    Compare Command(command_pct) vs Response(response_pct).
    Pass if Response stays within ±5% of Command; fail if it overshoots, undershoots, or exceeds ±5%.
    Output: Pass/Fail; For each Pass/Fail, display total count and its percentage; key timestamps; conclusion. Include one chart.
    ```

    **3. Check Power Supply Stability**
    ```
    Checks whether the problem is related to power instability.
    If Supply Voltage(supply_v) drops and Output(output_rpm) weakens, drops, or gets noisy at the same time, the issue may be power-related.
    If Output remains stable despite normal voltage variation, there is no strong evidence of power failure
    ```

    **4. Analyze Sensor Mismatch Behavior**
    ```
    Analyze uploaded "chart3_mode_sensor_mismatch.csv".
    Checks whether the issue is a sensor mismatch during a special mode.
    If Sensor1(sensor1_pct) and Sensor2(sensor2_pct) agree during normal operation but diverge mainly in one mode or event window, the issue may be mode-specific
    If disagreement exists across the full capture, it is persistent sensor disagreement
    ```
    """)

st.markdown("---")

with st.container():
    col1row1, col2row1 = st.columns(2)

    with col1row1:
        with st.container(height=ROW_HIGHT):
            chat_history_container = st.container(height=ROW_HIGHT - TEXTBOX_HIGHT)
            with chat_history_container:
                chat_history_container.title("Chat")
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                for msg in st.session_state["chat_history"]:
                    with chat_history_container.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            with st.container():
                user_input = st.chat_input("Ask something about your data...")
                if user_input:
                    st.session_state["chat_history"].append(
                        {"role": "user", "content": user_input}
                    )
                    _handle_chat_input(user_input)
                    st.rerun()

    with col2row1:
        with st.container(height=ROW_HIGHT):
            col2row1_plan_tab, col2row1_code_tab, col2row1_template_tab = st.tabs(
                ["Plan", "Code", "Template"]
            )

            with col2row1_plan_tab:
                ps = st.session_state.get("pipeline_state")
                plan_steps = ps.get("plan", []) if ps else []
                if plan_steps:
                    for i, step in enumerate(plan_steps):
                        st.text(f"{i + 1}. {step}")
                    # Guard: show button only when plan exists and not yet approved (AC #1, #3)
                    if not st.session_state.get("plan_approved", False):
                        if st.button("Execute Plan"):
                            st.session_state["plan_approved"] = True
                            st.session_state["pipeline_running"] = True
                            st.rerun()
                    else:
                        # Approved — pipeline execution wired in Story 3.x
                        st.success("✅ Plan approved.")
                        # Show Save as Template section after a successful run (AC #1)
                        if isinstance(ps, dict) and ps.get("execution_success"):
                            if not st.session_state.get("show_save_template_form", False):
                                if st.button("Save as Template", key="save_template_btn"):
                                    st.session_state["show_save_template_form"] = True
                                    st.rerun()
                            else:
                                # Inline name-entry form — no modal (UX requirement) (AC #2)
                                template_name = st.text_input(
                                    "Template name", key="template_name_input", max_chars=80
                                )
                                col_save, col_cancel = st.columns(2)
                                with col_save:
                                    if st.button("Confirm Save", key="confirm_save_template"):
                                        name = template_name.strip()
                                        if name:
                                            existing_names = [
                                                t.get("name")
                                                for t in st.session_state.get("saved_templates", [])
                                            ]
                                            if name in existing_names:
                                                st.warning(f'A template named "{name}" already exists. Choose a different name.')
                                            else:
                                                try:
                                                    save_template(
                                                        name,
                                                        ps.get("plan", []),
                                                        ps.get("generated_code", ""),
                                                    )
                                                    st.session_state["saved_templates"] = load_templates()
                                                    st.session_state["show_save_template_form"] = False
                                                    st.toast(f'Template "{name}" saved.')
                                                    st.rerun()
                                                except OSError as e:
                                                    st.error(f"Failed to save template: {e}")
                                        else:
                                            st.warning("Enter a name before saving.")
                                with col_cancel:
                                    if st.button("Cancel", key="cancel_save_template"):
                                        st.session_state["show_save_template_form"] = False
                                        st.rerun()
                else:
                    # Guard is intentional: qa/chat intents never populate plan,
                    # so the Execute button is never shown for those intents (AC #4, #5)
                    st.info(
                        "No plan generated yet. Submit a report-type request in the Chat panel."
                    )

            with col2row1_code_tab:
                # Code tab: editable code + manual re-execution (Story 5.2)
                # (sync: tests/test_code_viewer.py::get_code_for_display still valid for read path)
                ps = st.session_state.get("pipeline_state")
                generated_code = (
                    ps.get("generated_code", "")
                    if isinstance(ps, dict)
                    else ""
                )
                if generated_code:
                    edited_code = st_ace(
                        value=generated_code,
                        language="python",
                        theme="monokai",
                        readonly=False,
                        height=400,
                        key="code_editor",
                    )
                    # st_ace returns None on initial render before user interaction
                    current_code = edited_code if edited_code is not None else generated_code

                    if st.button("Re-run", key="rerun_code"):
                        re_exec_state = build_reexec_state(ps, current_code)
                        val_result = validate_code_node(re_exec_state)

                        if val_result.get("validation_errors"):
                            # Validation failed — show inline, do NOT execute (AC #4)
                            # Clear stale report so _execution_panel doesn't show old results
                            stale_clear = {
                                **ps,
                                "execution_success": False,
                                "report_charts": [],
                                "report_text": "",
                                "error_messages": val_result.get("error_messages", []),
                            }
                            st.session_state["pipeline_state"] = stale_clear
                            for msg in val_result.get("error_messages", []):
                                st.error(msg)
                        else:
                            # Validation passed — execute directly, bypassing LLM nodes (AC #2)
                            with st.spinner("Re-running code..."):
                                merged_state = {**re_exec_state, **val_result}
                                exec_result = execute_code(merged_state)
                                final_state = {**merged_state, **exec_result}
                            st.session_state["pipeline_state"] = final_state
                            st.rerun()  # _execution_panel() re-renders with new results (AC #3, #5)
                else:
                    st.info("Run an analysis to see the generated code here")

            with col2row1_template_tab:
                saved = st.session_state.get("saved_templates", [])
                if not saved:
                    st.info(
                        "No saved templates yet. Run an analysis and save it from the Plan tab."
                    )
                else:
                    for idx, tmpl in enumerate(saved):
                        st.write(f"**{tmpl.get('name', 'Unnamed')}**")
                        if st.button(
                            "Apply", key=f"apply_tmpl_{idx}_{tmpl.get('name', '')}"
                        ):
                            # Load template plan and code into pipeline_state (AC #4)
                            existing_ps = st.session_state.get("pipeline_state") or {}
                            st.session_state["pipeline_state"] = {
                                **existing_ps,
                                "plan": tmpl.get("plan", []),
                                "generated_code": tmpl.get("code", ""),
                                "execution_success": False,
                                "validation_errors": [],
                                "error_messages": [],
                                "report_charts": [],
                                "report_text": "",
                            }
                            st.session_state["plan_approved"] = False
                            st.session_state["show_save_template_form"] = False
                            st.rerun()

    col1row2, col2row2 = st.columns(2)

    with col1row2:
        with st.container(height=ROW_HIGHT):
            st.write("### User Data Set")

            uploaded_files = st.file_uploader(
                "Upload CSV files",
                type=["csv"],
                accept_multiple_files=True,
                key="csv_uploader",
            )

            if uploaded_files:
                _on_csv_upload(uploaded_files)
            else:
                # Files removed or never uploaded — clear large data warning and recovery state
                st.session_state["large_data_detected"] = False
                st.session_state["large_data_message"] = ""
                st.session_state["recovery_applied"] = ""  # Story 4.2
                if not st.session_state.get("uploaded_dfs"):
                    # No CSV uploaded yet — load the sample dataset as a starting point
                    if "df" not in st.session_state:
                        st.session_state.df = get_dataframe()

            # Display data editors — tabs if >1 file, single editor otherwise
            uploaded_dfs = st.session_state.get("uploaded_dfs", {})

            if len(uploaded_dfs) > 1:
                # Multi-file: render one tab per CSV
                tab_labels = list(uploaded_dfs.keys())
                tabs = st.tabs(tab_labels)
                for tab, (name, df) in zip(tabs, uploaded_dfs.items()):
                    with tab:
                        edited = st.data_editor(
                            df,
                            key=f"editable_table_{name}",
                            num_rows="dynamic",
                            on_change=handle_table_change,
                        )
                        # Write back edits to session — keep uploaded_dfs in sync
                        st.session_state["uploaded_dfs"][name] = edited
                # Keep st.session_state.df as first df for backward compat
                first_name = list(uploaded_dfs.keys())[0]
                st.session_state.df = st.session_state["uploaded_dfs"][first_name]
            elif len(uploaded_dfs) == 1:
                # Single file: no tabs — same as current behavior
                name, df = next(iter(uploaded_dfs.items()))
                edited_df = st.data_editor(
                    df,
                    key="editable_table",
                    num_rows="dynamic",
                    on_change=handle_table_change,
                )
                st.session_state["uploaded_dfs"][name] = edited_df
                st.session_state.df = edited_df
            else:
                # No uploads — show sample data
                if "df" not in st.session_state:
                    st.session_state.df = get_dataframe()
                edited_df = st.data_editor(
                    st.session_state.df,
                    key="editable_table",
                    num_rows="dynamic",
                    on_change=handle_table_change,
                )
                st.session_state.df = edited_df

    with col2row2:
        with st.container(height=ROW_HIGHT):
            _execution_panel()