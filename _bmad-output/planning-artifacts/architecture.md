---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - '_bmad-output/planning-artifacts/product-brief-data-analysis-copilot-2026-03-05.md'
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/prd-validation-report.md'
  - '_bmad-output/planning-artifacts/ux-design-specification.md'
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-03-08'
project_name: 'data-analysis-copilot'
user_name: 'Yan'
date: '2026-03-08'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
32 FRs across 8 categories:
- Data Input & Management (FR1–4): Multi-CSV upload, editable data table, session-scoped retention
- Natural Language Interface (FR5–9): Chat input, intent classification, plan generation, plan review, user-triggered execution
- Code Generation & Validation (FR10–13): Python code gen from plan, syntax/security/logic validation pre-execution
- Execution Engine (FR14–18): Isolated subprocess execution, failure detection, up to 3 retries + adaptive replanning, autonomous self-correction
- Report Output (FR19–22): Chart rendering, written trend analysis, stakeholder-readable labels, in-app display only
- Code Transparency (FR23–25): Code viewer, editable code, manual re-execution trigger
- Large Data Handling (FR26–29): Size detection, human-readable degradation message, at least one recovery path, no silent failures
- Observability (FR30–32): LangSmith tracing (env-var toggle), human-readable error output for developers

**Non-Functional Requirements:**
16 NFRs across 4 categories:
- Performance: App loads <5s; plan displayed <30s; full pipeline <15min; UI non-blocking during execution; size detection immediate
- Reliability: Standard workflow repeatable across runs; self-correction resolves most failures; no silent failures
- Security: Subprocess cannot access host filesystem beyond session dir; no outbound network calls from subprocess; code validated before execution; CSV data not persisted to disk; API keys from env vars only
- Integration: LLM unavailability → clear user error; LangSmith non-blocking; all Python deps explicitly pinned

**Scale & Complexity:**
Brownfield stabilization + one new capability (large data handling). No multi-tenancy, no cloud deployment, no authentication. Locally hosted, single-user, session-scoped.

- Primary domain: Local web app + AI agent pipeline
- Complexity level: Medium
- Estimated architectural components: ~10 (UI Layer, Session State Schema, Intent Classifier, Plan Generator, LangGraph Pipeline, Code Validator, Execution Sandbox, Large Data Handler, Report Renderer, LangSmith Observer)

### Technical Constraints & Dependencies

**Existing stack (from codebase):**
- Streamlit (UI framework + session state)
- LangGraph (state machine for agent pipeline)
- OpenAI API / GPT-4o (LLM for plan gen, code gen, self-correction)
- LangSmith (optional tracing, wrapped OpenAI client)
- streamlit_ace (code editor widget)
- pandas, matplotlib (data processing and chart rendering)
- Python subprocess (sandboxed code execution)
- dotenv (env var loading)

**Constraints:**
- No persistent storage (session_state only)
- No cloud deployment (localhost only)
- No dynamic library installation (pre-installed libs only in subprocess)
- No mobile breakpoints (desktop-first, 1280px min width)
- LangSmith must be optional and non-blocking

### Cross-Cutting Concerns Identified

1. **Async execution vs Streamlit rerun model** — the most critical architectural concern. Streamlit reruns the whole script on user interaction; a blocking LangGraph pipeline run will freeze the UI (violates NFR4). Requires threading, `st.status`, or job queue pattern.
2. **Session state schema** — all in-session data (CSVs, chat history, plan, generated code, execution status, report output) lives in `st.session_state`. The schema must be explicitly defined to prevent inconsistent state bugs.
3. **Error translation layer** — every exception from LLM failures, code execution, and API timeouts must be caught and translated to plain English before reaching the user (NFR8, FR29).
4. **Tab state preservation** — switching between Plan / Code / Template tabs must not re-trigger LLM generation. State must be cached in session_state, not recomputed.
5. **Subprocess security boundary** — the sandbox is the primary security perimeter. Code validation (FR11–13) and subprocess restrictions (NFR9–10) must be consistent and enforced pre-execution.
6. **LangSmith non-blocking integration** — tracing must be wrapped in try/except; failure to reach LangSmith must not propagate to the user experience.

## Starter Template Evaluation

### Primary Technology Domain

**Brownfield Python web application + AI agent pipeline** — the existing implementation is the starter. No template selection required; architectural decisions are constrained by and build on top of the existing stack.

### Existing Technology Baseline (Pinned from requirements.txt)

**Core Application Framework:**
- Python 3.12 runtime
- Streamlit 1.36.0 — UI framework, session state, server-side rendering
- streamlit-ace 0.1.1 — code editor widget (Plan/Code tab)
- streamlit-chat 0.1.1 — chat UI component

**AI Agent Pipeline:**
- LangGraph 0.3.18 — state machine orchestration for the analysis pipeline
- LangChain 0.3.27 / langchain-core 0.3.83 — LLM tooling and abstractions
- langchain-openai 0.3.35 — OpenAI integration layer
- langchain-experimental 0.3.4 — PythonREPLTool (currently imported; to be removed from production path in favour of subprocess sandbox)
- OpenAI SDK 1.109.1 — direct API client (GPT-4o)
- LangSmith 0.7.0 — optional tracing

**Data Processing & Visualization:**
- pandas 2.2.2 — CSV ingestion, data manipulation
- numpy 1.26.4 — numerical operations
- matplotlib 3.9.0 — chart generation inside subprocess

**Execution & Security:**
- Python `subprocess` (stdlib) — sandboxed code execution
- Python `ast` (stdlib) — syntax validation / static analysis

**Supporting Libraries:**
- pydantic 2.7.4 — data validation / typed state schemas
- python-dotenv 1.0.1 — env var loading
- duckduckgo_search 8.1.1 — search tool (currently wired in; out of MVP scope — to be removed or gated)
- tenacity 8.4.1 — retry logic (available; retry behaviour owned by LangGraph loop in production path)

### Architectural Decisions Established by Existing Stack

| Decision Area | Established Choice |
|---|---|
| Language & Runtime | Python 3.12 — type hints and async available |
| UI Model | Streamlit server-side rendering — full script reruns on each user interaction |
| State Management | `st.session_state` — sole in-session store; no DB; no persistence across refreshes |
| AI Pipeline Orchestration | LangGraph `StateGraph` — nodes are discrete pipeline stages; edges define retry/replan routing |
| LLM | OpenAI GPT-4o via `langchain-openai`, wrapped with LangSmith for optional tracing |
| Code Execution Sandbox | Python `subprocess` with restriction constraints — primary security boundary |
| Code Editor | `streamlit-ace` — Monaco-based editor embedded in Code tab |
| Dependency Management | `requirements.txt` fully pinned — ensures reproducibility across local installations |

### Version Concerns to Address

1. **Streamlit 1.36.0 (June 2024)** — `st.status` (pipeline progress UI) is available ✅. However `st.fragment` (partial reruns for non-blocking execution, available 1.37.0+) is NOT available. **Upgrade to Streamlit 1.40+ is recommended before implementing async pipeline pattern (NFR4).**
2. **langchain-experimental / PythonREPLTool** — currently imported but executes in-process without isolation. The `subprocess` sandbox is the correct production path. PythonREPLTool should be removed from the execution flow.
3. **duckduckgo_search** — imported and wired but out of MVP scope. Should be removed or explicitly gated to avoid unused dependency surface.

**Note:** First implementation story should resolve version concerns (Streamlit upgrade, dependency cleanup) before extending functionality.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
1. Async execution pattern — `@st.fragment` + Streamlit 1.40+ upgrade (unblocks NFR4)
2. LangGraph `PipelineState` schema — typed data contract across all graph nodes
3. Session state schema — all `st.session_state` keys explicitly defined

**Important Decisions (Shape Architecture):**
4. Subprocess security — import allowlist + per-session temp dir sandbox
5. Large data handling — dual threshold + uniform stride downsampling
6. Template persistence — `templates.json` (scoped exception to no-persistence constraint)

**Deferred Decisions (Post-MVP):**
- Report export (PDF/PNG) — explicitly out of scope
- Session persistence across refreshes — out of scope
- Cloud deployment / CI/CD — out of scope

### Data Architecture

**Session State (`st.session_state`):**

```python
{
    "uploaded_dfs": dict[str, pd.DataFrame],  # filename auto-extracted from UploadedFile.name
    "csv_temp_path": str | None,              # path to per-session temp CSV file
    "chat_history": list[dict],               # [{"role": "user"|"bot", "content": str}]
    "pipeline_state": PipelineState | None,   # written back after graph.invoke()
    "pipeline_running": bool,
    "plan_approved": bool,
    "active_tab": Literal["plan", "code", "template"],
    "saved_templates": list[dict],            # loaded from templates.json on startup
    "active_template": dict | None,
}
```

**LangGraph `PipelineState` (TypedDict flowing through all graph nodes):**

```python
class PipelineState(TypedDict):
    user_query: str
    csv_temp_path: str           # nodes load CSV from file as needed; not passed as data
    data_row_count: int
    intent: Literal["report", "qa", "chat"]
    plan: list[str]
    generated_code: str
    validation_errors: list[str]
    execution_output: str
    execution_success: bool
    retry_count: int             # max 3 before adaptive replan (FR16)
    replan_triggered: bool
    error_messages: list[str]    # translated error history (FR29)
    report_charts: list[bytes]   # PNG bytes via BytesIO from subprocess (FR19)
    report_text: str             # written trend analysis (FR20)
    large_data_detected: bool
    large_data_message: str
    recovery_applied: str
```

**Template Persistence:**
- Storage: `templates.json` in app root directory
- Format: `[{"name": str, "plan": list[str], "code": str}]`
- Loaded into `st.session_state["saved_templates"]` on app startup
- Written on "Save as Template" user action
- Rationale: deliberate scoped exception to no-persistence constraint — templates are user-created reusable assets

### Authentication & Security

**No authentication** — internal tool, single user, localhost only. Out of scope for MVP.

**Subprocess Security — two-layer model:**

**Layer 1 — AST pre-execution allowlist validation:**
- Permitted imports: `pandas`, `numpy`, `matplotlib`, `matplotlib.pyplot`, `math`, `statistics`, `datetime`, `collections`, `itertools`, `io`, `base64`
- Any import outside this list → validation failure → LangGraph retry with corrected prompt
- Blocked patterns: `eval()`, `exec()`, `__import__()`, `open()` with write modes, `os.*`, `sys.*`, `subprocess.*`, `socket.*`, `urllib.*`, `requests.*`

**Layer 2 — Subprocess launch constraints:**
- Working directory: `tempfile.mkdtemp()` per session — subprocess restricted to this dir only (NFR9)
- Env vars: no inheritance from parent process except whitelisted `PATH`, `PYTHONPATH`
- Timeout: 60 seconds enforced — runaway execution killed
- stdout/stderr: fully captured; never raw-displayed to user — error translation layer applied (NFR8)
- Subprocess cannot write to `templates.json` or any path outside its temp dir (NFR12)

### API & Communication Patterns

**No external API layer** — Streamlit is the UI; all communication is in-process or via:
- OpenAI API via `langchain-openai` — LLM calls for intent classification, plan generation, code generation, self-correction
- LangSmith tracing API — optional, non-blocking, always wrapped in `try/except`

**LangSmith integration pattern (NFR15):**
```python
try:
    # tracing call
except Exception:
    pass  # always silent — failure never surfaces to user
```

**LLM unavailability handling (NFR14):**
`OpenAI APIError` caught at pipeline entry point, translated to plain English message:
> "Unable to reach the AI service. Please check your API key and internet connection."

### Frontend Architecture

**Async execution model:** `@st.fragment` decorator isolates the pipeline execution panel. Only the execution fragment reruns during pipeline execution — chat panel and tabs remain interactive (NFR4). Requires Streamlit 1.40+.

**Four-panel layout:**
| Position | Panel | Streamlit Component |
|---|---|---|
| Top-left | Chat (fixed input, scrollable history) | `st.chat_input`, `st.chat_message` |
| Top-right | Plan / Code / Template tabs | `st.tabs` |
| Bottom-left | CSV uploader + editable data table | `st.file_uploader`, `st.data_editor` |
| Bottom-right | Report (charts + trend text) | `st.image`, `st.markdown` |

**Tab state preservation:** Plan, Code, and Template content stored in `st.session_state` — tab switches never re-trigger LLM generation (cross-cutting concern #4).

**Execution progress:** `st.status` context manager in the `@st.fragment` panel shows step-level pipeline status: _Classifying intent → Generating plan → Validating code → Executing → Rendering report_.

**Large data user message pattern (FR27–28):**
Inline message in report panel (no modals — anti-pattern per UX spec):
> "Your dataset has X rows / Y MB, which exceeds the visualization threshold. Automatically downsampling to 10,000 points using uniform stride. You can also filter your data in the table before running."

### Infrastructure & Deployment

- **Hosting:** Localhost only — `streamlit run streamlit_app.py`
- **No CI/CD, no Docker, no cloud** — out of scope for MVP
- **Environment config:** `.env` file via `python-dotenv`
  - Required: `OPENAI_API_KEY`
  - Optional: `LANGSMITH_API_KEY` (tracing disabled if absent)
- **Dependency management:** `requirements.txt` fully pinned; first story upgrades Streamlit to 1.40+

### Decision Impact Analysis

**Implementation Sequence:**
1. Dependency cleanup + Streamlit upgrade to 1.40+ _(unblocks `@st.fragment`)_
2. Define `PipelineState` TypedDict and LangGraph graph skeleton
3. Implement session state initialization with defined schema
4. Implement allowlist code validator (AST-based)
5. Implement subprocess sandbox with per-session temp dir
6. Implement large data detector (dual threshold check on upload)
7. Implement uniform stride downsampler + inline user message
8. Implement `@st.fragment` execution panel with `st.status` step progress
9. Implement template save/load with `templates.json`

**Cross-Component Dependencies:**
- `@st.fragment` requires Streamlit 1.40+ → upgrade is story 1 and unblocks story 8
- `csv_temp_path` in `PipelineState` is set during session init → session schema (story 3) must precede pipeline stories
- Allowlist validator runs before subprocess launch → validator (story 4) is a hard dependency of executor (story 5)
- Large data detection runs on CSV upload, before pipeline starts → story 6 must precede execution stories
- `templates.json` is the only intentional disk write → subprocess sandbox (story 5) must explicitly exclude this path

## Implementation Patterns & Consistency Rules

### Critical Conflict Points: 8 areas where AI agents could make different choices

### Naming Patterns

**Python conventions (applies everywhere):**
- Functions and variables: `snake_case` — e.g. `generate_plan`, `csv_temp_path`, `retry_count`
- Classes: `PascalCase` — e.g. `PipelineState`, `CodeValidator`
- Constants: `UPPER_SNAKE_CASE` — e.g. `MAX_RETRY_COUNT = 3`, `LARGE_DATA_ROW_THRESHOLD = 100_000`
- Private helpers: single leading underscore — e.g. `_translate_error`, `_build_prompt`

**`st.session_state` key naming — always `snake_case` string literals:**
```python
# CORRECT
st.session_state["pipeline_running"]
st.session_state["uploaded_dfs"]
st.session_state["plan_approved"]

# WRONG — never camelCase, never dot access on dynamic keys
st.session_state["pipelineRunning"]  # ❌
st.session_state.pipeline_running    # ❌ (dot access only for pre-defined Streamlit keys)
```

**LangGraph node function naming — verb_noun pattern:**
```python
# CORRECT
def classify_intent(state: PipelineState) -> dict: ...
def generate_plan(state: PipelineState) -> dict: ...
def generate_code(state: PipelineState) -> dict: ...
def validate_code(state: PipelineState) -> dict: ...
def execute_code(state: PipelineState) -> dict: ...
def handle_error(state: PipelineState) -> dict: ...
def render_report(state: PipelineState) -> dict: ...

# WRONG — noun_verb, gerunds, vague names
def code_generator(state): ...   # ❌
def running_code(state): ...     # ❌
def process(state): ...          # ❌
```

**LangGraph edge/node string identifiers — match function names exactly:**
```python
graph.add_node("classify_intent", classify_intent)   # string = function name
graph.add_edge("classify_intent", "generate_plan")
```

### Structure Patterns

**Module organisation (refactored from single-file):**
```
streamlit_app.py          # UI entry point only — layout, session init, @st.fragment panels
pipeline/
    __init__.py
    state.py              # PipelineState TypedDict definition
    graph.py              # LangGraph graph construction and compilation
    nodes/
        __init__.py
        intent.py         # classify_intent node
        planner.py        # generate_plan node
        codegen.py        # generate_code node
        validator.py      # validate_code node
        executor.py       # execute_code node + subprocess sandbox
        reporter.py       # render_report node
        error_handler.py  # handle_error node
utils/
    __init__.py
    session.py            # session state initialisation helpers
    large_data.py         # threshold detection + downsampling
    error_translation.py  # exception → plain English messages
    templates.py          # templates.json read/write
templates.json            # persisted user templates
.env                      # API keys (not committed)
requirements.txt          # pinned deps
```

**Session state initialisation — always in one place (`utils/session.py`):**
```python
def init_session_state():
    defaults = {
        "uploaded_dfs": {},
        "csv_temp_path": None,
        "chat_history": [],
        "pipeline_state": None,
        "pipeline_running": False,
        "plan_approved": False,
        "active_tab": "plan",
        "saved_templates": load_templates(),
        "active_template": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

### Format Patterns

**Chat message format — always this exact shape:**
```python
{"role": "user" | "bot", "content": str}

# WRONG
{"sender": "user", "text": "..."}    # ❌
{"type": "human", "message": "..."}  # ❌
```

**LangGraph node return — always return only changed keys (not full state):**
```python
def generate_plan(state: PipelineState) -> dict:
    return {"plan": [...], "intent": "report"}
    # NOT: return {**state, "plan": [...]}  — LangGraph merges automatically ❌
```

**Validation result — always return tuple `(is_valid: bool, errors: list[str])`:**
```python
def validate_code(code: str) -> tuple[bool, list[str]]:
    errors = []
    # ... AST checks ...
    return len(errors) == 0, errors

# Usage in node:
is_valid, errors = validate_code(state["generated_code"])
if not is_valid:
    return {"validation_errors": errors, "execution_success": False}
```

**Subprocess chart output — base64-encoded PNG via stdout, prefixed `CHART:`:**
```python
# Inside generated code (runs in subprocess):
import base64, io
buf = io.BytesIO()
plt.savefig(buf, format='png', bbox_inches='tight')
print("CHART:" + base64.b64encode(buf.getvalue()).decode())

# In executor.py — parse stdout for CHART: lines:
charts = []
for line in output.split('\n'):
    if line.startswith("CHART:"):
        charts.append(base64.b64decode(line[6:]))
return {"report_charts": charts, "execution_success": True}
```

### Communication Patterns

**Error translation — always through `utils/error_translation.py`, never inline:**
```python
# CORRECT
user_message = translate_error(exception)
return {"error_messages": state["error_messages"] + [user_message]}

# WRONG — never expose raw exceptions to UI layer
st.error(str(exception))                      # ❌
return {"error_messages": [repr(exception)]}  # ❌
```

**Error taxonomy (`translate_error` maps exceptions to these messages):**

| Exception type | User-facing message |
|---|---|
| `openai.APIError` | "Unable to reach the AI service. Check your API key and connection." |
| `openai.RateLimitError` | "AI service rate limit reached. Please wait a moment and try again." |
| `subprocess.TimeoutExpired` | "Analysis took too long and was stopped. Try a simpler request or subset your data." |
| `SyntaxError` in validation | "Generated code had a syntax error — retrying with a corrected approach." |
| Allowlist violation | "Generated code used a restricted operation — retrying with safer code." |
| All other `Exception` | "An unexpected error occurred. Check the developer console for details." |

**LangSmith tracing — `@traceable` on pipeline entry point only:**
```python
# pipeline/graph.py — trace the full pipeline invocation
@traceable(name="analysis_pipeline")
def run_pipeline(state: PipelineState) -> PipelineState:
    return compiled_graph.invoke(state)

# Individual nodes are NOT decorated — LangGraph traces them automatically
```

### Process Patterns

**Large data check — always on upload, never at execution time:**
```python
# In CSV upload handler (streamlit_app.py)
def on_csv_upload(files):
    dfs = {f.name: pd.read_csv(f) for f in files}
    combined_rows = sum(len(df) for df in dfs.values())
    combined_size_mb = sum(f.size for f in files) / 1_048_576

    if combined_rows >= 100_000 or combined_size_mb >= 20:
        st.session_state["large_data_detected"] = True
        # ... set message, apply downsampling before writing temp file
```

**Session state mutation — only in UI layer or `utils/session.py`; never inside `pipeline/`:**
```python
# CORRECT — UI layer writes to session state after pipeline completes
st.session_state["pipeline_running"] = True
result = run_pipeline(state)
st.session_state["pipeline_state"] = result
st.session_state["pipeline_running"] = False

# WRONG — pipeline modules must never import or write to st.session_state
import streamlit as st  # ❌ inside pipeline/nodes/executor.py
st.session_state["result"] = ...  # ❌
```

### Enforcement Guidelines

**All AI agents MUST:**
- Use `snake_case` for all Python identifiers (functions, variables, session keys, node string names)
- Return only changed keys from LangGraph nodes — never spread full state
- Route all exceptions through `utils/error_translation.py` before any user display
- Never import `streamlit` inside `pipeline/` or `utils/` modules (except `utils/session.py`)
- Never write to `st.session_state` from inside `pipeline/` modules
- Use `(bool, list[str])` tuple as the return type of all validation functions
- Prefix subprocess chart output lines with `CHART:` + base64-encoded PNG bytes

**Anti-patterns to explicitly avoid:**
```python
st.session_state["pipelineRunning"] = True     # ❌ camelCase key
st.error(str(e))                               # ❌ raw exception to user
return {**state, "plan": new_plan}             # ❌ spreading full state from node
import streamlit as st  # inside pipeline/     # ❌ streamlit in pipeline layer
result = run_pipeline(state)  # at top level   # ❌ blocking call outside @st.fragment
```

## Project Structure & Boundaries

### Complete Project Directory Structure

```
data-analysis-copilot/
├── streamlit_app.py              # UI entry point — layout, session init, @st.fragment panels
│                                 # ONLY file that imports streamlit
├── templates.json                # Persisted user templates (created on first save)
├── requirements.txt              # Fully pinned Python dependencies
├── .env                          # API keys — never committed
├── .env.example                  # Template for required env vars
├── .gitignore
├── README.md
│
├── pipeline/                     # AI agent pipeline — NO streamlit imports
│   ├── __init__.py
│   ├── state.py                  # PipelineState TypedDict definition
│   ├── graph.py                  # LangGraph StateGraph construction + run_pipeline()
│   └── nodes/
│       ├── __init__.py
│       ├── intent.py             # classify_intent node (FR6)
│       ├── planner.py            # generate_plan node (FR7)
│       ├── codegen.py            # generate_code node (FR10)
│       ├── validator.py          # validate_code node (FR11–13)
│       ├── executor.py           # execute_code node + subprocess sandbox (FR14–18)
│       ├── reporter.py           # render_report node (FR19–22)
│       └── error_handler.py      # handle_error node — retry/replan routing (FR15–17)
│
├── utils/
│   ├── __init__.py
│   ├── session.py                # init_session_state() — all st.session_state defaults
│   ├── large_data.py             # detect_large_data(), apply_uniform_stride() (FR26–28)
│   ├── error_translation.py      # translate_error() — exception → plain English (FR29, NFR8)
│   └── templates.py              # load_templates(), save_template() — templates.json I/O
│
├── tests/
│   ├── __init__.py
│   ├── test_validator.py         # Unit tests for allowlist validation logic
│   ├── test_large_data.py        # Unit tests for threshold detection + downsampling
│   ├── test_error_translation.py # Unit tests for error taxonomy mapping
│   └── test_executor.py          # Subprocess sandbox integration tests
│
├── UI_design/                    # Reference design assets (existing — do not modify)
│   ├── design1.png
│   └── design2.png
│
└── code-for-learning/            # Reference/learning code (existing — do not modify)
    ├── graph_workflow.py
    └── streamlit_app_langchain.py
```

### Architectural Boundaries

**UI Boundary (`streamlit_app.py`):**
- Only file that may import `streamlit`
- Owns all `st.session_state` reads and writes
- Calls `init_session_state()` once at app startup
- Invokes `run_pipeline()` only from within an `@st.fragment` decorated function
- Renders charts via `st.image(bytes)` for each item in `pipeline_state["report_charts"]`
- Handles CSV upload event → calls `detect_large_data()` → writes CSV to temp file

**Pipeline Boundary (`pipeline/`):**
- Zero streamlit imports — pure Python
- All I/O via `PipelineState` TypedDict fields only
- Nodes return `dict` of changed keys only — never `{**state, ...}`
- `graph.py` compiles the graph once at module load; `run_pipeline()` is the sole entry point
- LangSmith `@traceable` applied only on `run_pipeline()` in `graph.py`

**Utils Boundary (`utils/`):**
- Pure utility functions — no LangGraph imports
- Exception: `utils/session.py` may import streamlit (writes to `st.session_state`)
- All error translation happens here — no other module catches and displays exceptions directly

**Persistence Boundary:**
- `templates.json`: read by `utils/templates.py` on startup; written on Save action
- Subprocess temp dir: `tempfile.mkdtemp()` per pipeline run; cleaned up after execution
- Everything else is session-scoped and lost on browser refresh

### Requirements to Structure Mapping

| FR Category | Primary Files |
|---|---|
| Data Input & Management (FR1–4) | `streamlit_app.py` (upload handler), `utils/session.py`, `utils/large_data.py` |
| Natural Language Interface (FR5–9) | `pipeline/nodes/intent.py`, `pipeline/nodes/planner.py`, `streamlit_app.py` (chat panel) |
| Code Generation & Validation (FR10–13) | `pipeline/nodes/codegen.py`, `pipeline/nodes/validator.py` |
| Execution Engine (FR14–18) | `pipeline/nodes/executor.py`, `pipeline/nodes/error_handler.py`, `pipeline/graph.py` |
| Report Output (FR19–22) | `pipeline/nodes/reporter.py`, `streamlit_app.py` (report panel render) |
| Code Transparency (FR23–25) | `streamlit_app.py` (Code tab with `streamlit-ace` editor + re-run button) |
| Large Data Handling (FR26–29) | `utils/large_data.py`, `streamlit_app.py` (inline message in report panel) |
| Observability (FR30–32) | `pipeline/graph.py` (`@traceable`), `utils/error_translation.py` |

**Cross-Cutting Concerns → Files:**

| Concern | Files Involved |
|---|---|
| Session state schema | `utils/session.py` (init), `streamlit_app.py` (read/write) |
| Error translation | `utils/error_translation.py` — all nodes funnel exceptions here |
| Subprocess security | `pipeline/nodes/validator.py` (AST allowlist) + `pipeline/nodes/executor.py` (sandbox) |
| Tab state preservation | `streamlit_app.py` (reads `st.session_state["active_tab"]`; plan/code stored in `pipeline_state`) |
| LangSmith non-blocking | `pipeline/graph.py` (`try/except` wrapper around `@traceable`) |

### Integration Points

**Internal Data Flow:**
```
User types query → streamlit_app.py chat panel
  → st.session_state["chat_history"] updated
  → Execute clicked → @st.fragment panel invokes run_pipeline(initial_state)
  → LangGraph routes through nodes:
      classify_intent → generate_plan → generate_code
      → validate_code → [pass] → execute_code (subprocess sandbox)
                      → [fail ≤3] → handle_error → generate_code (retry)
                      → [fail >3] → handle_error → generate_plan (adaptive replan)
      → execute_code [success] → render_report → PipelineState returned
  → st.session_state["pipeline_state"] = result
  → streamlit_app.py renders report_charts + report_text in report panel
```

**External Integrations:**
- **OpenAI API** — called from `pipeline/nodes/` (intent, planner, codegen, error_handler) via `langchain-openai` `ChatOpenAI`
- **LangSmith API** — called transparently via `@traceable` in `pipeline/graph.py`; optional; non-blocking

**Subprocess Data Flow:**
```
execute_code node
  → writes CSV to tempfile.mkdtemp() dir
  → launches Python subprocess with generated code
  → subprocess reads CSV, generates matplotlib charts
  → prints "CHART:<base64_png>" for each chart + trend text to stdout
  → executor.py captures stdout, parses CHART: lines → list[bytes]
  → returns {"report_charts": [...], "report_text": "...", "execution_success": True}
  → temp dir cleaned up after execution
```

### Development Workflow

**Running the app:**
```bash
cp .env.example .env   # add OPENAI_API_KEY
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Running tests:**
```bash
python -m pytest tests/
```

**`.env.example`:**
```
OPENAI_API_KEY=                          # required
LANGSMITH_API_KEY=                       # optional — tracing disabled if absent
LANGCHAIN_TRACING_V2=true               # optional
LANGCHAIN_PROJECT=data_analysis_copilot # optional
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All technology choices are compatible and work together without conflicts:
- Streamlit 1.40+ + `@st.fragment` + LangGraph + OpenAI — established production combination
- `PipelineState` TypedDict is natively supported as LangGraph's state schema type
- `subprocess` sandbox + `ast` AST validator are complementary stdlib modules with no conflict
- `templates.json` write path is distinct from subprocess temp dir — no security boundary conflict
- LangSmith `try/except` wrapper ensures tracing failures never propagate to users

**Pattern Consistency:**
- All naming conventions are consistently `snake_case` across session keys, node names, and file names
- Node return pattern (changed keys only) is consistent with LangGraph's automatic state merge behaviour
- Error translation funnel (`utils/error_translation.py`) is the single path for all exceptions — no inline handling anywhere
- `CHART:` prefix pattern for subprocess chart output is consistent across codegen system prompt and executor stdout parser

**Structure Alignment:**
- Module boundaries (pipeline/nodes/ vs utils/ vs streamlit_app.py) map directly to the three-layer architecture: UI / Pipeline / Utilities
- `@st.fragment` isolation of the execution panel aligns with the UX specification's non-blocking execution requirement
- `init_session_state()` as the single initialisation point prevents state inconsistency across reruns

### Requirements Coverage Validation ✅

**Functional Requirements (32/32 covered):**

| FR Category | Coverage | Primary Location |
|---|---|---|
| FR1–4: Data Input & Management | ✅ | `streamlit_app.py`, `utils/session.py`, `utils/large_data.py` |
| FR5–9: Natural Language Interface | ✅ | `pipeline/nodes/intent.py`, `planner.py`, `streamlit_app.py` chat panel |
| FR10–13: Code Generation & Validation | ✅ | `pipeline/nodes/codegen.py`, `validator.py` |
| FR14–18: Execution Engine | ✅ | `pipeline/nodes/executor.py`, `error_handler.py`, `pipeline/graph.py` |
| FR19–22: Report Output | ✅ | `pipeline/nodes/reporter.py`, `streamlit_app.py` report panel |
| FR23–25: Code Transparency | ✅ | `streamlit_app.py` Code tab + `streamlit-ace` + re-run button |
| FR26–29: Large Data Handling | ✅ | `utils/large_data.py`, inline message in report panel |
| FR30–32: Observability | ✅ | `pipeline/graph.py` (`@traceable`), `utils/error_translation.py` |

**Non-Functional Requirements (16/16 covered):**

| NFR Group | Coverage | Mechanism |
|---|---|---|
| NFR1–5: Performance | ✅ | `@st.fragment` (NFR4), upload-time detection (NFR5), 60s subprocess timeout (NFR3) |
| NFR6–8: Reliability | ✅ | LangGraph retry/replan loop (NFR7), error translation layer (NFR8) |
| NFR9–13: Security | ✅ | Temp dir sandbox (NFR9–10), AST allowlist (NFR11), cleanup (NFR12), env vars (NFR13) |
| NFR14–16: Integration | ✅ | APIError handling (NFR14), LangSmith try/except (NFR15), pinned requirements.txt (NFR16) |

### Implementation Readiness Validation ✅

**Decision Completeness:** All 6 critical and important decisions are documented with rationale and concrete code examples. Zero undecided architectural questions remain.

**Structure Completeness:** All files and directories are explicitly named and mapped to specific FRs. No placeholder directories.

**Pattern Completeness:** All 8 identified conflict points have explicit patterns with correct and incorrect examples provided.

### Gap Analysis Results

**Critical Gaps: None**

**Important Gaps (2 — resolved here):**

**Gap 1 — LangGraph conditional edge routing (retry/replan logic):**
Explicit conditional routing for the self-correction loop must be implemented exactly as follows:

```python
# pipeline/graph.py

def route_after_execution(state: PipelineState) -> str:
    if state["execution_success"]:
        return "render_report"
    elif state["retry_count"] < 3:
        return "generate_code"   # retry with corrected prompt
    else:
        return "generate_plan"   # adaptive replan

graph.add_conditional_edges(
    "execute_code",
    route_after_execution,
    {
        "render_report": "render_report",
        "generate_code": "generate_code",
        "generate_plan": "generate_plan",
    }
)
```

**Gap 2 — FR21: Codegen node chart label requirement:**
`pipeline/nodes/codegen.py` system prompt MUST include the following instruction to GPT-4o:
> "Always include `plt.xlabel()`, `plt.ylabel()`, `plt.title()`, and `plt.tight_layout()` in every matplotlib chart. Labels must be descriptive and readable without engineering context — e.g., 'Voltage (V)' not 'v', 'Time (ms)' not 't'."

This is a prompt-level architectural constraint that must be present in the codegen node's system message.

**Nice-to-Have Gaps:**
- A `tests/conftest.py` with shared fixtures (sample CSVs, mock LLM responses) would accelerate test writing — not blocking for MVP

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (32 FRs, 16 NFRs, 4 user journeys)
- [x] Scale and complexity assessed (medium — brownfield stabilisation + one new capability)
- [x] Technical constraints identified (no auth, no cloud, session-only, LangSmith optional)
- [x] Cross-cutting concerns mapped and resolved (6 concerns)

**✅ Architectural Decisions**
- [x] Critical decisions documented with rationale and code examples
- [x] Technology stack fully specified with pinned versions
- [x] Security model defined (two-layer: AST allowlist + subprocess temp-dir sandbox)
- [x] Performance considerations addressed (`@st.fragment`, 60s timeout, upload-time size check)

**✅ Implementation Patterns**
- [x] Naming conventions established (snake_case, verb_noun nodes, UPPER_SNAKE constants)
- [x] Structure patterns defined (module boundaries, single session init location)
- [x] Communication patterns specified (error taxonomy, CHART: prefix, chat message format)
- [x] Process patterns documented (large data on upload, session mutation in UI layer only)

**✅ Project Structure**
- [x] Complete directory structure defined with all files explicitly named
- [x] Component boundaries established (UI / Pipeline / Utils three-layer model)
- [x] Integration points mapped (internal data flow, subprocess I/O, external APIs)
- [x] All FR categories mapped to specific files

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High** — all decisions are explicit, concrete, and mutually consistent. Both gaps are resolved within this document.

**Key Strengths:**
- Brownfield approach preserves existing working code; refactoring is additive, not destructive
- `PipelineState` TypedDict as the single data contract eliminates state ambiguity across nodes
- Three-layer boundary (UI / Pipeline / Utils) prevents circular dependencies between concerns
- Error translation as a centralised funnel ensures no raw exceptions ever reach users
- Explicit conditional edge routing for retry/replan prevents agents from guessing the loop logic
- Chart label requirement in codegen system prompt ensures FR21 compliance without extra code

**Areas for Future Enhancement (post-MVP):**
- `@st.fragment` upgrade path already in place — no rework needed to add streaming progress later
- `templates.json` could migrate to SQLite without changing the API (`utils/templates.py` is the only consumer)
- Subprocess sandbox could be hardened with OS-level process isolation for higher-security deployments

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented — no local interpretations
- Use implementation patterns and concrete examples as the source of truth for code style
- Respect module boundaries: never import `streamlit` inside `pipeline/`
- Use the error taxonomy table for all user-facing error messages — no ad-hoc strings
- Implement `route_after_execution` conditional edges exactly as specified in Gap 1

**First Implementation Priority:**
```bash
# Story 1: Dependency cleanup + Streamlit upgrade
pip install "streamlit>=1.40.0"
# Remove from requirements.txt and streamlit_app.py imports:
#   - langchain-experimental (PythonREPLTool)
#   - duckduckgo_search (out of MVP scope)
# Update requirements.txt with new pinned versions
streamlit run streamlit_app.py  # verify app still loads correctly
```
