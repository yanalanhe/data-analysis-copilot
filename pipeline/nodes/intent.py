# pipeline/nodes/intent.py
"""Intent classification node for the new pipeline.

NOTE: Never import streamlit in this file.
"""
from pipeline.state import PipelineState
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for a data analysis tool.
Classify the user's message into exactly one of these three categories:
- "report": The user wants to create a chart, visualization, analysis report, or any
  computation/aggregation of data (e.g., "create a chart of X vs Y", "analyze column X",
  "calculate correlation", "show trends in")
- "qa": The user wants a direct factual answer about the data without a full report
  (e.g., "what is the max value?", "how many rows?", "what is the average of column B?")
- "chat": General conversation, capability questions, or greetings
  (e.g., "hello", "what can you do?", "thank you")

Respond with ONLY one word: report, qa, or chat. No explanation, no punctuation."""


def classify_intent(state: PipelineState) -> dict:
    """Classify user intent as 'report', 'qa', or 'chat'.

    Returns only the changed key per LangGraph convention.
    Defaults to 'chat' on any LLM error.
    """
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        messages = [
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=state["user_query"]),
        ]
        response = llm.invoke(messages)
        raw = response.content.strip().lower()
        if raw in ("report", "qa", "chat"):
            intent = raw
        elif "report" in raw:
            intent = "report"
        elif "qa" in raw or "q&a" in raw:
            intent = "qa"
        else:
            intent = "chat"
        return {"intent": intent}
    except Exception as e:
        from utils.error_translation import translate_error
        error_msg = translate_error(e)
        return {
            "intent": "chat",  # safe fallback — pipeline continues
            "error_messages": list(state.get("error_messages", [])) + [error_msg],
        }
