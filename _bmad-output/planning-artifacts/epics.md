---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
status: complete
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/planning-artifacts/ux-design-specification.md'
---

# data-analysis-copilot - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for data-analysis-copilot, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Users can upload one or more CSV files in a single session
FR2: Users can view uploaded CSV data in an editable table within the UI
FR3: Users can edit data directly in the data table before running analysis
FR4: The system retains uploaded CSV data and chat history for the duration of a session
FR5: Users can submit analysis requests in natural language via a chat interface
FR6: The system classifies the intent of each query (report generation, simple Q&A, or general chat)
FR7: The system generates a step-by-step execution plan from a natural language analysis request
FR8: Users can review the generated execution plan before triggering execution
FR9: Users explicitly trigger plan execution — execution is not automatic
FR10: The system generates Python analysis code from the execution plan
FR11: The system validates generated code for syntax errors before execution
FR12: The system validates generated code for unsafe or potentially destructive operations before execution
FR13: The system validates generated code for logical correctness before execution
FR14: The system executes generated Python code in an isolated subprocess
FR15: The system detects code execution failures and initiates a retry with a corrected approach
FR16: The system retries failed code generation up to 3 times before triggering adaptive replanning
FR17: The system adaptively replans the analysis approach when repeated code generation attempts fail
FR18: The system completes standard analysis requests without requiring user intervention on failure
FR19: The system renders visual charts in a dedicated report panel from executed analysis code
FR20: The system renders written trend analysis in the report panel alongside charts
FR21: Report charts include clear labels, axis titles, and readable annotations sufficient for a non-technical stakeholder to act on
FR22: Users can view the complete report output within the application UI without exporting
FR23: Users can view the Python code generated to produce any report
FR24: Users can edit the generated Python code directly in the UI
FR25: Users can manually trigger re-execution of edited code
FR26: The system detects when an uploaded dataset exceeds a size threshold for effective visualization
FR27: The system displays a clear, human-readable message when dataset size causes degraded or unrenderable visualization
FR28: The system provides at least one recovery path when a dataset is too large — either automatic downsampling or a prompt to subset/reduce the data
FR29: The system surfaces a user-readable error message for all execution failures — no silent failures
FR30: The system logs all LLM calls and agent decisions to LangSmith when tracing is enabled
FR31: Developers can enable or disable LangSmith tracing via environment variable configuration
FR32: The system surfaces execution error information in a human-readable format to assist developer debugging

### NonFunctional Requirements

NFR1: The application loads and reaches an interactive state within 5 seconds of starting on localhost
NFR2: A generated execution plan is displayed in the UI within 30 seconds of submitting a natural language query
NFR3: The full execution pipeline (code generation → validation → execution → report render) completes within 15 minutes for a typical batch dataset
NFR4: The UI remains responsive during pipeline execution — it does not freeze or block user input while the pipeline is running
NFR5: Dataset size detection and any resulting user message are surfaced immediately upon or before execution — no unresponsive UI states during size evaluation
NFR6: The standard workflow (upload CSV → NL query → plan → execute → report) completes without failure on repeated runs with the same input on locally hosted instances
NFR7: The self-correction loop resolves code generation failures without user intervention for the majority of standard analysis requests
NFR8: All execution failures surface a user-readable message — no silent failures, no raw stack traces presented to end users
NFR9: Generated Python code executes in an isolated subprocess that cannot access the host filesystem beyond the session working directory
NFR10: Generated Python code cannot make outbound network calls from within the subprocess
NFR11: The system validates generated code for unsafe operations (file writes, network calls, OS commands) before execution
NFR12: CSV data uploaded in a session does not persist to disk beyond the session lifecycle
NFR13: LLM API keys are loaded from environment variables and are never hardcoded or logged in application output
NFR14: When the LLM API is unavailable, the system surfaces a clear user-facing error message rather than hanging or crashing silently
NFR15: LangSmith tracing is non-blocking — if LangSmith is unreachable or unconfigured, the application continues to function normally
NFR16: The application specifies all required Python library dependencies explicitly, ensuring consistent behavior across different local installations

### Additional Requirements

**From Architecture:**
- Upgrade Streamlit to 1.40+ (required for `@st.fragment` non-blocking execution, unblocks NFR4) — first story priority
- Remove `langchain-experimental` / `PythonREPLTool` from execution flow (replaced by subprocess sandbox)
- Remove or gate `duckduckgo_search` dependency (currently wired in but out of MVP scope)
- Define `PipelineState` TypedDict in `pipeline/state.py` as the typed data contract across all LangGraph nodes
- Implement `init_session_state()` in `utils/session.py` as the single session state initialisation point — all st.session_state keys defined here
- Implement AST-based allowlist code validator (`pipeline/nodes/validator.py`) before subprocess execution (Layer 1 security)
- Implement subprocess sandbox with per-session `tempfile.mkdtemp()` temp dir (`pipeline/nodes/executor.py`) — Layer 2 security; 60s timeout enforced
- Implement large data dual threshold detection on CSV upload (100,000 rows OR 20MB), not at execution time (`utils/large_data.py`)
- Implement uniform stride downsampling to 10,000 points for oversized datasets
- Implement `@st.fragment` decorator on execution panel for non-blocking UI interaction
- Implement `templates.json` persistence for user-saved analysis templates (`utils/templates.py`)
- Implement `route_after_execution` conditional edge routing in `pipeline/graph.py` (retry_count < 3 → generate_code; retry_count >= 3 → generate_plan adaptive replan; success → render_report)
- Codegen system prompt MUST include chart label requirements: `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, `plt.tight_layout()` with descriptive labels (FR21)
- All exceptions must route through `utils/error_translation.py` — no inline exception handling anywhere else
- Subprocess chart output format: `CHART:<base64_png>` prefix on stdout lines, parsed by executor.py
- LangSmith `@traceable` applied only on `run_pipeline()` in `pipeline/graph.py`, always wrapped in try/except
- Module boundary enforced: `pipeline/` modules never import streamlit (exception: `utils/session.py`)
- Fully pinned `requirements.txt` for reproducibility across local installations
- **Brownfield project — no starter template; existing implementation is the baseline**

**From UX Design:**
- Four-panel Streamlit layout: chat interface (top-left), Plan/Code/Template tabs (top-right), CSV uploader + editable data table (bottom-left), report panel (bottom-right)
- Desktop-first, 1280px minimum width — no mobile breakpoints required for MVP
- No modal dialogs — all error and large-data messages displayed inline within relevant panels
- Execution progress displayed via `st.status` with step-level updates: Classifying intent → Generating plan → Validating code → Executing → Rendering report
- Tab state must be preserved on switch — no re-triggering LLM generation when switching between Plan/Code/Template tabs
- "Save as template" button visible in Plan tab after a successful run
- Default/sample CSV pre-loaded for zero-friction onboarding (first-time users can run immediately)
- Keyboard-primary interaction model (Enter to send chat messages; mouse for uploads and buttons)
- Basic accessibility: keyboard navigation, readable color contrast, descriptive labels on interactive elements
- Error messages use plain language: state what happened + offer one clear next action — never a raw traceback

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 1 | Multi-CSV upload |
| FR2 | Epic 1 | Editable data table view |
| FR3 | Epic 1 | In-table data editing |
| FR4 | Epic 1 | Session-scoped data retention |
| FR5 | Epic 2 | Natural language chat interface |
| FR6 | Epic 2 | Intent classification |
| FR7 | Epic 2 | Execution plan generation |
| FR8 | Epic 2 | Plan review before execution |
| FR9 | Epic 2 | User-triggered execution |
| FR10 | Epic 3 | Python code generation |
| FR11 | Epic 3 | Syntax validation |
| FR12 | Epic 3 | Security/unsafe operation validation |
| FR13 | Epic 3 | Logic correctness validation |
| FR14 | Epic 3 | Isolated subprocess execution |
| FR15 | Epic 3 | Failure detection + retry |
| FR16 | Epic 3 | Up to 3 retries before replan |
| FR17 | Epic 3 | Adaptive replanning |
| FR18 | Epic 3 | Autonomous self-correction |
| FR19 | Epic 3 | Chart rendering in report panel |
| FR20 | Epic 3 | Written trend analysis |
| FR21 | Epic 3 | Stakeholder-readable chart labels |
| FR22 | Epic 3 | In-app report display |
| FR23 | Epic 5 | Code viewer |
| FR24 | Epic 5 | Editable generated code |
| FR25 | Epic 5 | Manual code re-execution |
| FR26 | Epic 4 | Large dataset size detection |
| FR27 | Epic 4 | Human-readable degradation message |
| FR28 | Epic 4 | Recovery path (downsample or subset) |
| FR29 | Epic 3 | No silent failures — readable errors for all execution failures |
| FR30 | Epic 6 | LangSmith LLM call logging |
| FR31 | Epic 6 | Env-var toggle for tracing |
| FR32 | Epic 6 | Human-readable error output for developers |

## Epic List

### Epic 1: Application Foundation & Data Input
Engineers can install the app on any local machine, upload one or more CSV files, and review their data in an editable table — ready to begin analysis. All shared architectural scaffolding (module structure, session state schema, dependency cleanup) is established so all future epics build on a stable base.
**FRs covered:** FR1, FR2, FR3, FR4
**Also addresses:** Streamlit 1.40+ upgrade, `langchain-experimental` removal, `duckduckgo_search` removal, `PipelineState` TypedDict definition, `init_session_state()`, three-layer module structure, four-panel UI layout, sample CSV for onboarding

### Epic 2: Natural Language Request & Plan Review
Engineers type an analysis request in plain English, see a numbered execution plan appear in the Plan tab within 30 seconds, and explicitly choose to execute it — staying in control throughout.
**FRs covered:** FR5, FR6, FR7, FR8, FR9

### Epic 3: Automated Code Execution & Visual Report
Engineers click Execute and receive a visual report with rendered charts and written trend analysis — with the system handling code generation, validation, subprocess execution, and autonomous self-correction on failure, with plain-English errors surfaced for all failures.
**FRs covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22, FR29
**Also addresses:** `@st.fragment` non-blocking execution panel, `st.status` step-level progress, conditional edge routing (retry/replan), error translation taxonomy, `CHART:` base64 subprocess output, subprocess sandbox

### Epic 4: Large Data Resilience
Engineers uploading large datasets see an immediate human-readable warning with at least one recovery option (auto-downsample or subset prompt) — no silent failures, no raw tracebacks, no frozen UI.
**FRs covered:** FR26, FR27, FR28
**Also addresses:** Dual threshold (100K rows / 20MB) on upload, uniform stride downsampling to 10K points, inline message in report panel (no modals)

### Epic 5: Code Transparency & Template System
Engineers can inspect the Python code behind any report, edit it directly in the UI, re-run modified code, and save successful analysis patterns as named templates for future sessions.
**FRs covered:** FR23, FR24, FR25
**Also addresses:** `streamlit-ace` Code tab editor, `templates.json` persistence, "Save as Template" in Plan tab

### Epic 6: Developer Observability & Resilience
Developers enable LangSmith tracing via environment variable to trace all LLM calls and agent decisions, diagnose failures in minutes, and rely on clear error messages when the LLM API is unreachable.
**FRs covered:** FR30, FR31, FR32

---

## Epic 1: Application Foundation & Data Input

Engineers can install the app on any local machine, upload one or more CSV files, and review their data in an editable table — ready to begin analysis. All shared architectural scaffolding is established so all future epics build on a stable base.

### Story 1.1: Dependency Cleanup & Streamlit Upgrade

As a developer,
I want the codebase cleaned up with out-of-scope dependencies removed and Streamlit upgraded to 1.40+,
So that the app has a stable, production-ready foundation and the `@st.fragment` non-blocking execution pattern is available for subsequent stories.

**Acceptance Criteria:**

**Given** the updated `requirements.txt`
**When** I run `pip install -r requirements.txt`
**Then** all dependencies install without conflicts

**Given** the cleaned codebase
**When** I run `streamlit run streamlit_app.py`
**Then** the app starts and loads successfully with no import errors

**Given** the installed Streamlit version
**When** I check `streamlit --version`
**Then** it is 1.40.0 or higher

**Given** the cleaned codebase
**When** I search for `langchain_experimental`, `PythonREPLTool`, and `duckduckgo_search`
**Then** none appear in any production code import or execution path

---

### Story 1.2: Three-Layer Module Structure, PipelineState & Session Schema

As a developer,
I want the codebase organized into three architectural layers (UI / pipeline / utils) with `PipelineState` TypedDict and session state schema explicitly defined,
So that all subsequent development follows consistent boundaries and the data contract between components is unambiguous.

**Acceptance Criteria:**

**Given** the refactored codebase
**When** I inspect the file tree
**Then** all required files exist: `streamlit_app.py`, `pipeline/__init__.py`, `pipeline/state.py`, `pipeline/graph.py`, `pipeline/nodes/__init__.py`, `pipeline/nodes/intent.py`, `pipeline/nodes/planner.py`, `pipeline/nodes/codegen.py`, `pipeline/nodes/validator.py`, `pipeline/nodes/executor.py`, `pipeline/nodes/reporter.py`, `pipeline/nodes/error_handler.py`, `utils/__init__.py`, `utils/session.py`, `utils/error_translation.py`, `utils/large_data.py`, `utils/templates.py`

**Given** `pipeline/state.py`
**When** I import `PipelineState`
**Then** it is a TypedDict with all required fields: `user_query`, `csv_temp_path`, `data_row_count`, `intent`, `plan`, `generated_code`, `validation_errors`, `execution_output`, `execution_success`, `retry_count`, `replan_triggered`, `error_messages`, `report_charts`, `report_text`, `large_data_detected`, `large_data_message`, `recovery_applied`

**Given** `utils/session.py`
**When** `init_session_state()` is called
**Then** all `st.session_state` keys are initialized with correct defaults: `uploaded_dfs: {}`, `csv_temp_path: None`, `chat_history: []`, `pipeline_state: None`, `pipeline_running: False`, `plan_approved: False`, `active_tab: "plan"`, `saved_templates: []`, `active_template: None`

**Given** `init_session_state()` is called on every Streamlit rerun
**When** keys already exist in session state
**Then** existing values are preserved — initialization is idempotent

**Given** any file inside `pipeline/`
**When** I check all import statements
**Then** no file imports `streamlit` (only exception permitted: `utils/session.py`)

---

### Story 1.3: Four-Panel Layout & CSV Upload with Editable Data Table

As an engineer,
I want to upload one or more CSV files and see them in an editable data table within a four-panel app layout,
So that I can review and correct my data before running any analysis.

**Acceptance Criteria:**

**Given** the app is open at localhost
**When** I view the UI on a 1280px-wide screen
**Then** I see four panels: chat interface (top-left), Plan/Code/Template tabs (top-right), CSV uploader + editable data table (bottom-left), report panel (bottom-right) — all visible without horizontal scrolling

**Given** the CSV uploader
**When** I drag-and-drop one or more CSV files (or use Browse)
**Then** the files are accepted, loaded into pandas DataFrames, and stored in `st.session_state["uploaded_dfs"]` keyed by filename

**Given** one or more uploaded CSVs
**When** I view the data table area
**Then** data is displayed in an editable `st.data_editor` table

**Given** the editable data table
**When** I change a cell value and click outside the cell
**Then** the change is reflected in the displayed table

**Given** a CSV upload event
**When** the upload handler processes the file(s)
**Then** `st.session_state["csv_temp_path"]` is set to the path of a per-session temp CSV file

**Given** the app starts for the first time with no user data
**When** I view the data table
**Then** a pre-loaded sample dataset is shown so I can immediately try the tool without uploading my own CSV

**Given** the app loads
**When** I measure time from `streamlit run` to interactive state
**Then** it reaches interactive state within 5 seconds (NFR1)

---

## Epic 2: Natural Language Request & Plan Review

Engineers type an analysis request in plain English, see a numbered execution plan appear in the Plan tab within 30 seconds, and explicitly choose to execute it — staying in control throughout.

### Story 2.1: Natural Language Chat Interface & Intent Classification

As an engineer,
I want to type analysis requests in a chat interface and have the system classify my intent,
So that the right pipeline path is triggered for my query type.

**Acceptance Criteria:**

**Given** the chat panel (top-left)
**When** I type a message and press Enter
**Then** my message appears in the chat history with role `"user"`

**Given** a submitted query
**When** the system processes it
**Then** a response appears in the chat history with role `"bot"`

**Given** `st.session_state["chat_history"]`
**When** I interact with other panels or switch tabs
**Then** the chat history remains intact and fully visible

**Given** a submitted query with report intent (e.g., "create a chart of voltage vs time")
**When** `classify_intent` runs
**Then** `pipeline_state["intent"]` is set to `"report"`

**Given** a submitted query with Q&A intent (e.g., "what is the max value in column A?")
**When** `classify_intent` runs
**Then** `pipeline_state["intent"]` is set to `"qa"` and the system responds directly in the chat without generating a plan

**Given** a general conversation message (e.g., "hello")
**When** `classify_intent` runs
**Then** `pipeline_state["intent"]` is set to `"chat"` and the system responds directly in the chat with no plan or Execute button shown

---

### Story 2.2: Execution Plan Generation & Display

As an engineer,
I want to see a numbered execution plan appear in the Plan tab within 30 seconds of submitting a report-type request,
So that I can review exactly what the system will do before approving it.

**Acceptance Criteria:**

**Given** I submit a natural language request with `"report"` intent
**When** `generate_plan` runs
**Then** a step-by-step plan is generated and stored in `pipeline_state["plan"]`

**Given** the Plan tab
**When** a plan is available
**Then** it displays as a numbered list of human-readable sentences — plain English, no code, no jargon (e.g., "1. Load voltage and current data", "2. Calculate summary statistics", "3. Plot voltage vs time")

**Given** a submitted report request
**When** I wait for the plan to appear
**Then** it is displayed in the Plan tab within 30 seconds (NFR2)

**Given** the Plan tab is displaying a plan
**When** I click the Code or Template tab and return to Plan
**Then** the plan content is preserved — no LLM call is re-triggered (tab state preservation)

---

### Story 2.3: Plan Review & User-Triggered Execution

As an engineer,
I want to review the generated plan and explicitly click Execute to start the analysis,
So that I stay in control and nothing runs without my approval.

**Acceptance Criteria:**

**Given** a generated plan is displayed in the Plan tab
**When** I view the panel
**Then** an "Execute" button is visible and clickable

**Given** I click the Execute button
**When** the click is processed
**Then** `st.session_state["plan_approved"]` is set to `True` and `st.session_state["pipeline_running"]` is set to `True`, signalling the pipeline to start

**Given** I have NOT clicked Execute
**When** viewing the app at any point after a plan is shown
**Then** no code is generated or executed automatically — execution is strictly user-triggered (FR9)

**Given** a `"qa"` intent query
**When** the system responds
**Then** no multi-step plan is displayed and no Execute button is shown — the response appears directly in chat

**Given** a `"chat"` intent query
**When** the system responds
**Then** no plan and no Execute button are shown — conversation is handled directly in chat

---

## Epic 3: Automated Code Execution & Visual Report

Engineers click Execute and receive a visual report with rendered charts and written trend analysis — with the system handling code generation, validation, subprocess execution, and autonomous self-correction on failure, with plain-English errors surfaced for all failures.

### Story 3.1: Error Translation Layer & No Silent Failures

As an engineer,
I want all pipeline failures to surface a plain-English message in the UI rather than a raw traceback,
So that I always know what happened and what to do next.

**Acceptance Criteria:**

**Given** `utils/error_translation.py` is implemented
**When** an `openai.APIError` is passed to `translate_error()`
**Then** it returns: `"Unable to reach the AI service. Check your API key and connection."`

**Given** an `openai.RateLimitError`
**When** passed to `translate_error()`
**Then** it returns: `"AI service rate limit reached. Please wait a moment and try again."`

**Given** a `subprocess.TimeoutExpired`
**When** passed to `translate_error()`
**Then** it returns: `"Analysis took too long and was stopped. Try a simpler request or subset your data."`

**Given** a `SyntaxError` from AST validation
**When** passed to `translate_error()`
**Then** it returns: `"Generated code had a syntax error — retrying with a corrected approach."`

**Given** an allowlist violation
**When** passed to `translate_error()`
**Then** it returns: `"Generated code used a restricted operation — retrying with safer code."`

**Given** any other `Exception`
**When** passed to `translate_error()`
**Then** it returns: `"An unexpected error occurred. Check the developer console for details."` — never a raw `repr(exception)`

**Given** any error surfaced to the user in the UI
**When** I inspect the entire codebase
**Then** no `st.error(str(e))` or `st.error(repr(e))` calls exist — all errors route through `utils/error_translation.py`

---

### Story 3.2: Python Code Generation from Plan

As an engineer,
I want the system to generate Python analysis code from the approved execution plan,
So that I don't have to write any code myself.

**Acceptance Criteria:**

**Given** an approved execution plan in `pipeline_state["plan"]`
**When** the `generate_code` node runs in `pipeline/nodes/codegen.py`
**Then** valid Python code is produced and stored in `pipeline_state["generated_code"]`

**Given** the `generate_code` node's system prompt
**When** it instructs GPT-4o to generate chart code
**Then** the prompt explicitly requires `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, and `plt.tight_layout()` with descriptive human-readable labels (e.g., "Voltage (V)" not "v") — satisfying FR21

**Given** generated code that produces a chart
**When** it is executed in the subprocess
**Then** each chart is output as `"CHART:" + base64.b64encode(png_bytes).decode()` on stdout

**Given** the `generate_code` node running with a retry context (`retry_count > 0`)
**When** it constructs the prompt
**Then** it includes information about the previous failure to guide a better attempt

---

### Story 3.3: AST Allowlist Code Validator

As a developer,
I want generated code validated for syntax errors and unsafe operations before execution,
So that malicious or broken code never reaches the subprocess.

**Acceptance Criteria:**

**Given** generated code
**When** `validate_code()` runs in `pipeline/nodes/validator.py`
**Then** it returns a `tuple[bool, list[str]]` — `(True, [])` for valid code, `(False, [errors])` for invalid

**Given** code with a syntax error
**When** `validate_code()` runs
**Then** it returns `(False, ["Syntax error: ..."])` without executing anything

**Given** code containing an import outside the allowlist (e.g., `import os`, `import socket`)
**When** `validate_code()` runs
**Then** it returns `(False, [error_message])` — only `pandas`, `numpy`, `matplotlib`, `matplotlib.pyplot`, `math`, `statistics`, `datetime`, `collections`, `itertools`, `io`, `base64` are permitted

**Given** code containing blocked patterns (`eval()`, `exec()`, `__import__()`, `open()` with write modes, `os.*`, `sys.*`, `subprocess.*`, `socket.*`, `urllib.*`, `requests.*`)
**When** `validate_code()` runs
**Then** it returns `(False, [error_message])`

**Given** clean code with only allowed imports and no blocked patterns
**When** `validate_code()` runs
**Then** it returns `(True, [])`

**Given** a validation failure `(False, errors)`
**When** the pipeline processes the result
**Then** `translate_error()` is called on the error, `retry_count` is incremented, and the pipeline routes back to `generate_code`

---

### Story 3.4: Subprocess Sandbox Execution

As an engineer,
I want validated code executed in an isolated subprocess with a timeout,
So that generated code cannot affect my machine or persist data outside the session.

**Acceptance Criteria:**

**Given** code that passes all validation checks
**When** `execute_code` runs in `pipeline/nodes/executor.py`
**Then** a per-session temp directory is created via `tempfile.mkdtemp()` and the subprocess runs within it

**Given** the subprocess
**When** it runs
**Then** it has no access to the host filesystem outside the temp directory (NFR9) and no parent environment variables except whitelisted `PATH` and `PYTHONPATH` (NFR10)

**Given** a subprocess running longer than 60 seconds
**When** the timeout fires
**Then** the subprocess is killed, `subprocess.TimeoutExpired` is caught, `translate_error()` is called, and the message is appended to `pipeline_state["error_messages"]`

**Given** successful subprocess execution
**When** stdout is parsed
**Then** lines beginning with `CHART:` are base64-decoded into `bytes` and stored in `pipeline_state["report_charts"]`; remaining stdout text is stored in `pipeline_state["report_text"]`; `pipeline_state["execution_success"]` is set to `True`

**Given** execution failure (non-zero exit code or exception)
**When** the error is processed
**Then** `pipeline_state["execution_success"]` is set to `False` and a translated error message is appended to `pipeline_state["error_messages"]`

**Given** execution completes (success or failure)
**When** cleanup runs
**Then** the temp directory is deleted and CSV data does not persist to disk (NFR12)

---

### Story 3.5: Self-Correcting Retry & Adaptive Replan Loop

As an engineer,
I want the system to automatically retry failed code generation up to 3 times and adaptively replan when all retries are exhausted,
So that standard analysis requests succeed without me having to debug or intervene.

**Acceptance Criteria:**

**Given** `pipeline/graph.py` with the compiled LangGraph `StateGraph`
**When** I inspect the node connections
**Then** all nodes are wired: `classify_intent → generate_plan → generate_code → validate_code → execute_code`, with `render_report` connected via conditional edges on `execute_code`

**Given** `route_after_execution` in `pipeline/graph.py`
**When** `execution_success` is `True`
**Then** it returns `"render_report"`

**Given** `route_after_execution`
**When** `execution_success` is `False` and `retry_count < 3`
**Then** it returns `"generate_code"` and `retry_count` is incremented

**Given** `route_after_execution`
**When** `execution_success` is `False` and `retry_count >= 3`
**Then** it returns `"generate_plan"` and `replan_triggered` is set to `True`

**Given** `graph.add_conditional_edges` in `pipeline/graph.py`
**When** I inspect the implementation
**Then** it matches exactly: `graph.add_conditional_edges("execute_code", route_after_execution, {"render_report": "render_report", "generate_code": "generate_code", "generate_plan": "generate_plan"})`

**Given** any retry or replan event
**When** the error is caught
**Then** a human-readable message is appended to `pipeline_state["error_messages"]` via `translate_error()` — never a raw exception repr

---

### Story 3.6: Non-Blocking Execution Panel & Visual Report Rendering

As an engineer,
I want to see pipeline progress in real-time and receive rendered charts and written trend analysis in the report panel after execution, while the rest of the UI stays interactive,
So that I can see what's happening and immediately act on my results.

**Acceptance Criteria:**

**Given** the execution panel in `streamlit_app.py`
**When** I inspect the implementation
**Then** it is decorated with `@st.fragment`, isolating reruns to only the execution panel (NFR4)

**Given** pipeline execution is in progress
**When** I view the execution panel
**Then** a `st.status` context manager shows step-level progress: "Classifying intent → Generating plan → Validating code → Executing → Rendering report"

**Given** pipeline execution is running
**When** I type in the chat panel or switch tabs
**Then** the chat panel and tabs remain interactive — the UI does not freeze (NFR4)

**Given** successful execution with `report_charts` containing chart bytes
**When** the report panel renders
**Then** each chart is displayed using `st.image(chart_bytes)` in the report panel (bottom-right)

**Given** successful execution with `report_text`
**When** the report panel renders
**Then** the written trend analysis is displayed using `st.markdown(report_text)` below the charts

**Given** the rendered charts
**When** I view them
**Then** each chart has a visible title, labelled x-axis, and labelled y-axis with descriptive text — not single-letter variable names (FR21)

**Given** `st.session_state["pipeline_running"]` is set to `True`
**When** the `@st.fragment` panel invokes `run_pipeline()`
**Then** `st.session_state["pipeline_state"]` is updated with the result after completion and `pipeline_running` is reset to `False`

---

## Epic 4: Large Data Resilience

Engineers uploading large datasets see an immediate human-readable warning with at least one recovery option — no silent failures, no raw tracebacks, no frozen UI.

### Story 4.1: Large Dataset Detection & Inline Warning

As an engineer,
I want to see a clear inline message immediately when I upload a dataset that exceeds the visualization threshold,
So that I know what's happening before any analysis runs and can decide what to do.

**Acceptance Criteria:**

**Given** I upload CSV files with combined row count >= 100,000 OR combined size >= 20MB
**When** the upload handler in `streamlit_app.py` processes the files
**Then** `detect_large_data()` from `utils/large_data.py` is called and returns `True`

**Given** large data is detected
**When** I view the report panel (bottom-right)
**Then** an inline message appears — no modal or popup — stating: "Your dataset has X rows / Y MB, which exceeds the visualization threshold."

**Given** CSV files with combined row count < 100,000 AND combined size < 20MB
**When** I upload them
**Then** no warning is shown and the session proceeds normally with no degraded-path flag set

**Given** large data detection
**When** the check runs
**Then** it executes on CSV upload — before any pipeline execution attempt (NFR5)

**Given** the detection check running on upload
**When** I view the UI
**Then** it remains fully responsive — no blocking or freezing during detection (NFR5)

---

### Story 4.2: Auto-Downsampling Recovery Path

As an engineer,
I want the system to automatically downsample my large dataset to a manageable size and offer a manual subset alternative,
So that I can still get a useful visualization and analysis even with very large CSV files.

**Acceptance Criteria:**

**Given** large data is detected and the inline warning is shown
**When** I view the warning message
**Then** at least one recovery action is offered: an "Auto-downsample to 10,000 points" button is clearly visible (FR28)

**Given** I click the auto-downsample button
**When** `apply_uniform_stride()` from `utils/large_data.py` runs
**Then** uniform stride sampling reduces the combined dataset to 10,000 rows before writing the session temp CSV file

**Given** auto-downsampling has been applied
**When** I run analysis
**Then** the pipeline runs on the downsampled data and produces charts and trend analysis successfully

**Given** downsampling has been applied and the report panel shows results
**When** I view the report
**Then** a note is visible alongside the charts: "Downsampled to 10,000 points using uniform stride" — so I understand the tradeoff

**Given** the inline large data warning
**When** I read it
**Then** it also suggests filtering the data in the editable data table as an alternative recovery path (FR28)

**Given** no recovery action is taken and I attempt to run the pipeline with large data
**When** the pipeline processes the request
**Then** a clear user-readable message is surfaced — no silent failure, no raw traceback (NFR8, FR29)

---

## Epic 5: Code Transparency & Template System

Engineers can inspect the Python code behind any report, edit it directly in the UI, re-run modified code, and save successful analysis patterns as named templates for future sessions.

### Story 5.1: Code Viewer in streamlit-ace Editor

As an engineer,
I want to view the Python code generated for any analysis in the Code tab,
So that I can inspect what the system did and build trust in the output.

**Acceptance Criteria:**

**Given** a completed analysis
**When** I click the Code tab
**Then** the generated Python code from `pipeline_state["generated_code"]` is displayed in a `streamlit-ace` Monaco editor

**Given** the Code tab
**When** I switch to it from the Plan tab and back again
**Then** the code content is preserved without re-generating — it reads from session state, not a fresh LLM call

**Given** no analysis has been run yet
**When** I click the Code tab
**Then** the editor shows a placeholder message: "Run an analysis to see the generated code here"

**Given** the Code tab is visible
**When** I view it at any screen width >= 1280px
**Then** the editor is fully visible without horizontal scrolling and syntax is highlighted

---

### Story 5.2: Editable Code & Manual Re-Execution

As an engineer,
I want to edit the generated Python code directly in the Code tab and re-run it manually,
So that I can correct or extend the analysis without starting the entire workflow over.

**Acceptance Criteria:**

**Given** code is displayed in the Code tab editor
**When** I edit the code directly in the editor
**Then** my changes are reflected in the editor buffer in real time

**Given** I have edited the code
**When** I click a "Re-run" button in the Code tab
**Then** the modified code is sent through `validate_code()` and `execute_code` — bypassing intent classification and plan generation

**Given** the re-run succeeds
**When** execution completes
**Then** new charts and trend analysis replace the previous report panel output

**Given** the re-run fails validation (unsafe operation or syntax error)
**When** the validator catches it
**Then** a plain-English error message appears inline — no subprocess execution occurs and no raw traceback is shown

**Given** the re-run fails in the subprocess
**When** the error is caught
**Then** a translated error message appears in the report panel via `utils/error_translation.py`

---

### Story 5.3: Template Save & Reuse

As an engineer,
I want to save a successful analysis as a named template and re-apply it to future datasets,
So that I can reuse my best analysis patterns without retyping them each session.

**Acceptance Criteria:**

**Given** a successful analysis has completed
**When** I view the Plan tab
**Then** a "Save as Template" button is visible

**Given** I click "Save as Template"
**When** I enter a template name and confirm
**Then** the template (plan + code) is written to `templates.json` via `utils/templates.py` and immediately appears in the Template tab list

**Given** the Template tab
**When** I open it
**Then** all previously saved templates are listed by name

**Given** I select a saved template from the Template tab and click "Apply"
**When** the template is loaded
**Then** the template's plan is displayed in the Plan tab and the template's code is loaded into the Code tab editor

**Given** the app starts
**When** `init_session_state()` runs
**Then** `load_templates()` from `utils/templates.py` is called and saved templates are loaded into `st.session_state["saved_templates"]` automatically

**Given** the subprocess sandbox running generated code
**When** it executes
**Then** it cannot write to `templates.json` — template writes only occur from the UI layer via `utils/templates.py` (NFR9)

---

## Epic 6: Developer Observability & Resilience

Developers enable LangSmith tracing via environment variable to trace all LLM calls and agent decisions, diagnose failures in minutes, and rely on clear error messages when the LLM API is unreachable.

### Story 6.1: LangSmith Tracing Integration

As a developer,
I want to enable LangSmith tracing via environment variable and have all LLM calls and agent decisions captured in a trace,
So that I can diagnose pipeline failures in minutes rather than hours.

**Acceptance Criteria:**

**Given** `LANGSMITH_API_KEY` and `LANGCHAIN_TRACING_V2=true` are set in `.env`
**When** the app runs a pipeline invocation
**Then** the full trace is visible in the LangSmith dashboard showing the invocation chain (FR30)

**Given** `LANGSMITH_API_KEY` is NOT set
**When** the app starts and runs the standard workflow
**Then** it functions normally with no tracing-related errors, warnings, or UI impact (NFR15, FR31)

**Given** `pipeline/graph.py`
**When** I inspect the implementation
**Then** `@traceable(name="analysis_pipeline")` is applied only to `run_pipeline()` — individual nodes are traced automatically by LangGraph without additional decoration

**Given** a LangSmith connection failure during a run
**When** the tracing call throws any exception
**Then** it is silently caught (`try: ... except Exception: pass`) and the pipeline continues without surfacing any error to the user (NFR15)

**Given** `.env.example` in the project root
**When** I inspect it
**Then** it documents all four keys: `OPENAI_API_KEY` (required), `LANGSMITH_API_KEY` (optional), `LANGCHAIN_TRACING_V2` (optional), `LANGCHAIN_PROJECT` (optional)

**Given** API keys in `.env`
**When** I inspect the application code
**Then** no API key values are hardcoded or appear in any log output — all are loaded from environment variables via `python-dotenv` (NFR13)

---

### Story 6.2: LLM API Resilience & Developer Error Reporting

As a developer,
I want the app to surface clear errors when the LLM API is unavailable and provide human-readable error output for debugging,
So that I can quickly diagnose and resolve issues without reading raw stack traces.

**Acceptance Criteria:**

**Given** the OpenAI API is unreachable or returns an `openai.APIError`
**When** the pipeline runs
**Then** the user sees: "Unable to reach the AI service. Check your API key and connection." — not a raw exception (NFR14)

**Given** a pipeline failure at any node
**When** the error is caught and translated
**Then** `pipeline_state["error_messages"]` contains a human-readable description of what failed — visible to developers via the LangSmith trace (FR32)

**Given** `OPENAI_API_KEY` is missing from `.env`
**When** I submit a query
**Then** the error message identifies the missing key and provides an actionable next step ("Add OPENAI_API_KEY to your .env file")

**Given** the app is run without any LangSmith configuration
**When** it starts and I run the standard workflow (upload → query → execute → report)
**Then** startup is clean, the workflow completes successfully, and no warnings about missing optional configuration appear (NFR15, NFR16)

**Given** `requirements.txt`
**When** I inspect it
**Then** all Python library dependencies are explicitly pinned to exact versions — ensuring consistent behavior across local installations (NFR16)


