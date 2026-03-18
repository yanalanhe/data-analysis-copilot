import os
import time

import streamlit as st
import pandas as pd

from dotenv import load_dotenv
from langsmith.wrappers import wrap_openai
from langsmith import Client as LangSmithClient
from streamlit_ace import st_ace
from openai import OpenAI

from utils.error_translation import translate_error
from utils.reexec import build_reexec_state
from utils.templates import save_template, load_templates
from utils.data_upload import on_csv_upload, apply_downsample
from services.chat import handle_chat_input
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
# Shared UI helpers
# ─────────────────────────────────────────────

def get_stream(sentence):
    for word in sentence.split():
        yield word + " "
        time.sleep(0.05)


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
if "formatted_output" not in st.session_state:
    st.session_state.formatted_output = ""

# LangGraph structure printed once per session
from pipeline.legacy_agent import langgraph_app, _print_langgraph_structure
if "langgraph_initialized" not in st.session_state:
    _print_langgraph_structure(langgraph_app)
    st.session_state.langgraph_initialized = True


# ─────────────────────────────────────────────
# Execution panel (Story 3.6)
# ─────────────────────────────────────────────

@st.fragment
def _execution_panel() -> None:
    """Non-blocking execution panel decorated with @st.fragment.

    @st.fragment isolates reruns to this panel only — the chat panel and tabs
    remain interactive during pipeline execution (NFR4).
    """
    st.markdown('<div id="conclusions-section"></div>', unsafe_allow_html=True)
    st.write("### Conclusions")

    if st.session_state.pop("scroll_to_conclusions", False):
        st.components.v1.html(
            "<script>window.parent.document.getElementById('conclusions-section')"
            ".scrollIntoView({behavior:'smooth'});</script>",
            height=0,
        )


    # Story 4.1 + 4.2: Inline large data warning with recovery options (no modal, FR27, FR28)
    large_data = st.session_state.get("large_data_detected", False)
    recovery = st.session_state.get("recovery_applied", "")

    if large_data:
        base_msg = st.session_state.get("large_data_message", "")
        filter_hint = " You can also filter your data in the editable data table before running analysis."
        st.warning(base_msg + filter_hint)

        if recovery != "downsampled":
            if st.button("Auto-downsample to 10,000 points"):
                apply_downsample()
                st.rerun()
        else:
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
            lines = [l.strip() for l in report_text.splitlines() if l.strip()]
            st.markdown("\n".join(f"- {line}" for line in lines))
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

st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)

st.title("🔌 Circuit Board Data Analysis Tool")

with st.expander("📖 Usage Examples", expanded=False):
    st.write("Enter the following prompt to the chatbot:")
    st.markdown("""
    ```   
    1. Generate a scatter plot for columns A vs B.
    2. Generate a scatter plot for columns A vs C.
    3. Label the axes and the title of each scatter plot for clear understanding.
    4. Plot python_mpl.tool_how, way to make scatter plot.
    5. Observe the relationship between A and B.
    6. Observe the relationship between A and C.
    7. Draw conclusions about these relationships based on the scatter plots.
    8. Present conclusions about the scatter plots.
    9. Present conclusions about the relationships between columns A, B, and C.
    10. Include the scatter plots in the report to support your conclusions.
    ```
    """)

#st.markdown("---")

with st.container():
    col1row1, col2row1 = st.columns(2)

    with col1row1:
        with st.container(height=ROW_HIGHT):
            chat_history_container = st.container(height=ROW_HIGHT - TEXTBOX_HIGHT)
            with chat_history_container:
                st.write("### Chatbot")
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
                    handle_chat_input(user_input)
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
                            st.session_state["scroll_to_conclusions"] = True
                            st.rerun()
                    else:
                        st.success("✅ Plan approved.")
                        # Show Save as Template section after a successful run (AC #1)
                        if isinstance(ps, dict) and ps.get("execution_success"):
                            if not st.session_state.get("show_save_template_form", False):
                                if st.button("Save as Template", key="save_template_btn"):
                                    st.session_state["show_save_template_form"] = True
                                    st.rerun()
                            else:
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
                            st.rerun()
                else:
                    st.info("Run an analysis to see the generated code here")

            with col2row1_template_tab:
                ps = st.session_state.get("pipeline_state")

                # Save controls — shown when execution succeeded
                if isinstance(ps, dict) and ps.get("execution_success"):
                    st.write("#### Save Current Analysis as Template")
                    if not st.session_state.get("show_save_template_form", False):
                        if st.button("Save as Template", key="save_template_btn_tab"):
                            st.session_state["show_save_template_form"] = True
                            st.rerun()
                    else:
                        template_name = st.text_input(
                            "Template name", key="template_name_input_tab", max_chars=80
                        )
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("Confirm Save", key="confirm_save_template_tab"):
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
                            if st.button("Cancel", key="cancel_save_template_tab"):
                                st.session_state["show_save_template_form"] = False
                                st.rerun()
                    st.divider()

                # Saved templates list
                saved = st.session_state.get("saved_templates", [])
                if not saved:
                    st.info(
                        "No saved templates yet. Run an analysis and use the Save button above."
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
                on_csv_upload(uploaded_files)
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