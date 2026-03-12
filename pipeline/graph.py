# pipeline/graph.py
"""LangGraph pipeline graph construction and run_pipeline entry point.

Wires all pipeline nodes into a LangGraph StateGraph with retry/replan
conditional edges. Provides run_pipeline() as the sole entry point.

Graph topology:
  classify_intent → generate_plan → generate_code → validate_code_node
      → execute_code
           ├── success → render_report → END
           ├── failure (retry_count < 3) → generate_code
           └── failure (retry_count >= 3) → generate_plan (adaptive replan)

retry_count is incremented inside execute_code on failure paths.
route_after_execution reads the already-incremented retry_count.

NOTE: Never import streamlit in this file.
"""
from langgraph.graph import END, START, StateGraph

from pipeline.nodes.codegen import generate_code
from pipeline.nodes.executor import execute_code
from pipeline.nodes.intent import classify_intent
from pipeline.nodes.planner import generate_plan
from pipeline.nodes.reporter import render_report
from pipeline.nodes.validator import validate_code_node
from pipeline.state import PipelineState

try:
    from langsmith import traceable as _traceable
except ImportError:  # pragma: no cover
    def _traceable(name=None, **kwargs):  # type: ignore[misc]
        """Fallback identity decorator when langsmith is unavailable."""
        def decorator(fn):
            return fn
        return decorator


_MAX_REPLAN_RETRY = 6  # 3 retries + 3 replans; prevents infinite loop


def route_after_execution(state: PipelineState) -> str:
    """Conditional routing function called after execute_code completes.

    Reads execution_success and retry_count (already incremented by execute_code
    on failure) to determine the next graph node.

    Returns:
        "render_report"  — execution succeeded, OR max replans exhausted
        "generate_code"  — execution failed, retry_count < 3; retry code generation
        "generate_plan"  — execution failed, 3 <= retry_count < 6; adaptive replan
    """
    if state.get("execution_success"):
        return "render_report"
    retry = state.get("retry_count", 0)
    if retry < 3:
        return "generate_code"
    elif retry < _MAX_REPLAN_RETRY:
        return "generate_plan"
    else:
        return "render_report"


# ---------------------------------------------------------------------------
# Build the StateGraph
# ---------------------------------------------------------------------------

_builder = StateGraph(PipelineState)

# --- Register nodes (string name matches function name exactly) ---
_builder.add_node("classify_intent", classify_intent)
_builder.add_node("generate_plan", generate_plan)
_builder.add_node("generate_code", generate_code)
_builder.add_node("validate_code_node", validate_code_node)
_builder.add_node("execute_code", execute_code)
_builder.add_node("render_report", render_report)

# --- Linear edges: classify_intent → generate_plan → generate_code
#     → validate_code_node → execute_code ---
_builder.add_edge(START, "classify_intent")
_builder.add_edge("classify_intent", "generate_plan")
_builder.add_edge("generate_plan", "generate_code")
_builder.add_edge("generate_code", "validate_code_node")
_builder.add_edge("validate_code_node", "execute_code")

# --- Conditional edges from execute_code (AC #5 exact specification) ---
_builder.add_conditional_edges(
    "execute_code",
    route_after_execution,
    {
        "render_report": "render_report",
        "generate_code": "generate_code",
        "generate_plan": "generate_plan",
    },
)

# --- Terminal edge ---
_builder.add_edge("render_report", END)

# Compile once at module load (reused for every run_pipeline call)
compiled_graph = _builder.compile()


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

@_traceable(name="analysis_pipeline")
def run_pipeline(state: PipelineState) -> PipelineState:
    """Execute the full analysis pipeline via LangGraph.

    This is the sole entry point called from streamlit_app.py within an
    @st.fragment decorated function. Returns the final PipelineState after
    the graph completes all nodes.

    LangSmith @traceable is applied here only — individual nodes are traced
    automatically by LangGraph (NFR15: tracing failures are non-blocking).

    Args:
        state: Initial PipelineState containing user_query, csv_temp_path,
               data_row_count, and other initialized fields.

    Returns:
        Final PipelineState with report_charts, report_text, and all pipeline
        fields populated after graph completion.
    """
    try:
        result = compiled_graph.invoke(state)
        return result
    except Exception as e:
        # Surface unexpected errors to state — never crash the UI layer
        from utils.error_translation import translate_error  # late import to avoid cycles
        error_msg = translate_error(e)
        return {
            **state,
            "execution_success": False,
            "error_messages": list(state.get("error_messages", [])) + [error_msg],
        }
