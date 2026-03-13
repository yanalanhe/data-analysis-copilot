# pipeline/nodes/planner.py
"""Execution plan generation node.

NOTE: Never import streamlit in this file.
"""
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pipeline.state import PipelineState

_PLAN_SYSTEM_PROMPT = """You are an execution plan generator for a data analysis tool.
Given a user's analysis request and their dataset information, create a clear,
numbered step-by-step execution plan.

Rules:
- Each step must be a plain English sentence — no code, no technical jargon
- Steps should be concrete and actionable (e.g., "Load voltage and current columns",
  NOT "Process the data")
- Include data loading, computation, and visualization steps as appropriate
- Output ONLY the numbered list, one step per line
- Format: "1. Step description" on each line
- Typically 3-8 steps for most analysis requests"""


def generate_plan(state: PipelineState) -> dict:
    """Generate a step-by-step execution plan from the user query.

    Returns only changed keys per LangGraph convention.
    """
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)

        content = f"User request: {state['user_query']}"
        csv_metadata = state.get("csv_metadata", "")
        if csv_metadata:
            content += f"\n\n{csv_metadata}"

        messages = [
            SystemMessage(content=_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]

        response = llm.invoke(messages)
        raw = response.content.strip()
        steps = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+\.\s*", "", line)
            if cleaned:
                steps.append(cleaned)
        if not steps:
            steps = [raw]
        return {"plan": steps}
    except Exception as e:
        from utils.error_translation import translate_error
        error_msg = translate_error(e)
        return {
            "plan": [],
            "error_messages": list(state.get("error_messages", [])) + [error_msg],
        }
