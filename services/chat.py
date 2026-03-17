"""Chat service layer.

Handles intent routing, LLM response generation, and pipeline state
construction.  All functions that call the OpenAI API on behalf of chat
interactions live here, keeping streamlit_app.py free of LLM logic.
"""

import os
import tempfile

import streamlit as st
import pandas as pd

from dotenv import load_dotenv
from langsmith import traceable
from openai import OpenAI

load_dotenv()

_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────
# Pipeline state builder
# ─────────────────────────────────────────────

def make_initial_pipeline_state(user_input: str) -> dict:
    """Build a complete PipelineState dict with all 18 fields.

    Builds csv_metadata string from uploaded_dfs for LLM context.
    When no CSV is uploaded, the default sample dataset is written to a temp
    file so the pipeline can reference it by filename in generated code.
    """
    from pathlib import Path

    uploaded_dfs = st.session_state.get("uploaded_dfs", {})
    csv_temp_paths = st.session_state.get("csv_temp_paths", {})

    # No uploaded files — expose the default/sample dataframe to the pipeline
    if not csv_temp_paths and "df" in st.session_state:
        default_path = st.session_state.get("_default_csv_temp_path")
        if not default_path or not Path(default_path).exists():
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv", prefix="sample_data_"
            )
            st.session_state.df.to_csv(tmp.name, index=False)
            tmp.close()
            st.session_state["_default_csv_temp_path"] = tmp.name
            default_path = tmp.name
        csv_temp_paths = {"dataset.csv": default_path}
        uploaded_dfs = {"dataset.csv": st.session_state.df}

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


# ─────────────────────────────────────────────
# LLM response helpers
# ─────────────────────────────────────────────

def generate_qa_response(user_input: str) -> str:
    """Call LLM with dataset context to answer a factual question about the data."""
    try:
        df = st.session_state["df"] if "df" in st.session_state else None
        if df is not None:
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
        response = _openai_client.chat.completions.create(
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


def generate_chat_response(user_input: str) -> str:
    """Call LLM to respond to general conversation, including chat history for context."""
    try:
        history_messages = []
        for msg in st.session_state.get("chat_history", []):
            role = "assistant" if msg["role"] == "bot" else msg["role"]
            history_messages.append({"role": role, "content": msg["content"]})

        response = _openai_client.chat.completions.create(
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


def handle_chat_input(user_input: str) -> None:
    """Orchestrate intent classification and route to appropriate response handler."""
    st.session_state["plan_approved"] = False
    st.session_state["pipeline_running"] = False

    from pipeline.nodes.intent import classify_intent
    from pipeline.nodes.planner import generate_plan

    pipeline_state = make_initial_pipeline_state(user_input)

    try:
        intent_result = classify_intent(pipeline_state)
        intent = intent_result.get("intent", "chat")
    except Exception:
        intent = "chat"

    pipeline_state = {**pipeline_state, "intent": intent}
    st.session_state["pipeline_state"] = pipeline_state

    if intent == "report":
        plan_result = generate_plan(pipeline_state)
        pipeline_state = {**pipeline_state, **plan_result}
        st.session_state["pipeline_state"] = pipeline_state
        bot_msg = (
            "I've created an execution plan for your request. "
            "Check the Plan tab to review it."
        )
        st.session_state["chat_history"].append({"role": "bot", "content": bot_msg})
    elif intent == "qa":
        answer = generate_qa_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": answer})
    else:  # "chat"
        response = generate_chat_response(user_input)
        st.session_state["chat_history"].append({"role": "bot", "content": response})


# ─────────────────────────────────────────────
# Legacy chatbot response (pre-pipeline flow)
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
        from pipeline.legacy_agent import execute_plan

        def _get_stream(sentence):
            import time
            for word in sentence.split():
                yield word + " "
                time.sleep(0.05)

        st.write_stream(
            _get_stream("Got it, here is a plan to create report for this request of yours:")
        )
        result = session_state.df.to_csv()
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
            _get_stream(
                "📝 If you like the plan, please click on 'Execute Plan' button on the 'Plan' tab in the top right panel. Or feel free to ask me to revise the plan in this chat"
            )
        )
        session_state.plan = response
    else:
        response = st.write_stream(
            (lambda s: (w + " " for w in s.split()))(stream.choices[0].message.content)
        )

    return response
