# Run these in terminal

## Setup virtual environment for python

```
python3.12 -m venv .venv
```

```
source .venv/bin/activate
```

## Install BMad Method once and use everywhere:

```bash
npx bmad-method install --directory /path/to/project --modules bmm --tools claude-code --yes
```

# Run in Claude Code

## Open Claude Code Extention Chatbot

Open Claude Code extension Chatbot in your AI IDE

## Initial chat

On the Claude Code Chatbot, run the initial slash command:

```
/bmad-help
```

which directs what to do next

## Phase 1 Analysis

```
/bmad-bmm-create-product-brife
```

Note: Answer questions raised from running the above command

What are your product vision, target users, success metrics, and scope. 

 Enter background and pain points:

```
1. Background
Enterprise electronics engineers must identify and repair problems on circuit boards — a time-consuming, labor-intensive process requiring review of large amounts of tabular data.

2. Pain Points
- Reviewing large volumes of tabular data manually
- Complex, step-by-step troubleshooting workflow is inefficient
```

What does the data look like?

```
User can upload a csv or use the default csv data like:
  "A": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
  "B": [15, 25, 35, 45, 55, 65, 75, 85, 95, 105],
  "C": [5, 15, 25, 35, 45, 55, 65, 75, 85, 95],
```

What's the current workflow?

```
1. Load data - Edit or paste CSV data in the bottom-left data editor

2. Ask a question - Type in the chat box (e.g., "Create a report analyzing sales trends"

3. Review the plan - The AI generates a step-by-step analysis plan in the Plan tab

4. Execute - Click "Execute Plan" to run the analysis

5. View results - Charts and summaries appear in the AI Generated Report panel
```

What are the features of this product?

```
- Interactive Data Editor - Load and edit CSV data directly in the browser
- AI Chat Interface - Ask questions about your data in plain English
- Automated Report Generation - Request analysis reports and the AI creates a step-by-step plan, generates Python code, validates it, and displays the results
- Smart Intent Classification - Automatically routes between report generation, simple Q&A, and general chat
- Self-Correcting Code Execution - LangGraph workflow with up to 3 retry attempts and adaptive replanning on failure
- LangSmith Tracing - Optional observability for debugging LLM calls and agent workflows

```

What are the users journey?
Note: Provide users journeys even not asked from running BMad command

```
Journey 1: Primary User – Success Path (Sam)

Opening scene: Sam has just finished a circuit test run and has three CSVs (e.g. voltage, current, time). She used to spend hours in Excel building charts and writing up trends. She wants a report in minutes, not hours.

Rising action: She opens the locally hosted app, uploads the three CSVs, then types in natural language: "Report with voltage vs time and current vs time, as well as analyzing the trends." She reviews the request (and any plan/summary the system shows, if we add that). She hits Run.

Climax: The agents run, generate the analysis and charts, and assemble the report. The UI shows the report with two charts (voltage vs time, current vs time) and trend analysis. She can read and use it immediately.

Resolution: She gets a shareable or exportable report in ~15 minutes instead of ~2 hours. She feels the product "gets" what she asked for and delivers without manual chart-building.

Journey 2: Primary User – Edge Case (Large Data)

Opening scene: Sam has a test run that produced very large CSVs (e.g. high sample rate, long capture). She uploads them and asks for the same kind of report (voltage vs time, current vs time, trend analysis).

Rising action: She uploads the files and hits Run. The system runs but struggles: graphs are slow, unreadable (e.g. too many points), or the run times out. The product doesn't handle the scale well.

Climax: The system surfaces the problem instead of failing silently: e.g. a message that data is large, that graphing may be slow or degraded, or a suggestion to downsample/sample/summarize. Sam sees what went wrong and what her options are.

Resolution: Sam can recover in one or more of these ways (to be decided in design): (a) the system automatically downsamples or summarizes for visualization and still produces a report; (b) the system suggests "use a subset" or "reduce rows" and she filters/subsets and retries; (c) she gets a clear warning up front so she can split the data or reduce it before running. Her expectation: the product doesn't leave her stuck when "the data is really big."
```

What are success criteria?

```
User Success

1. Time-to-report: Engineers achieve report creation in ~15 minutes instead of ~2 hours for a typical batch.
- Charts without manual grind: They can get to "the right chart" quickly; the system handles the mechanics (data → graph) while they stay in control of what's being analyzed and why.
- Aha moment: Using natural language to describe what they want (e.g. "create a report with charts for X vs Y") and getting a concrete plan and then a report with charts—without writing code or building Excel charts by hand.

2. Business Success
- Internal validation: The product can generate a simple report with internal testers, running **reliably locally**.
- Proof point:** "This is working" = internal testers successfully produce at least one end-to-end report (upload → natural language → report with charts) on their own machines.

3. Technical Success
- Reliability: Runs reliably when hosted locally (no flaky runs for the core flow).
- Execution model: User triggers execution (e.g. click); agents run, produce the report, and the result is shown in the frontend.

4. Measurable Outcomes
- Report creation time: target ≤ 15 minutes for a typical batch (vs ~2 hours today).
- Capability: Natural language → plan → report with charts works for internal testers.
- Environment: Local (locally hosted web app or desktop); stable, repeatable runs.
```

## Phase 2 Create PRD
Note: Open a completely new conversation on the Claude Code Chatbot
```
/bmad-bmm-create-prd
```

After initial PRD created, run:
```
/bmad-bmm-validate-prd
```

UX Design
Open a completely new conversation on the Claude Code Chatbot, run:
```
/bmad-bmm-create-ux-design
```

## Phase 3 Solutioning

Create Atchitecture
```
/bmad-bmm-create-architecture
```

Create Epics and Stories
Open a completely new conversation on the Claude Code Chatbot, run:
```
/bmad-bmm-create-epics-and-stories
```

Create Story Files
Open a completely new conversation on the Claude Code Chatbot, run:
```
/bmad-bmm-create-story
```

Check Implementation Readiness 
```
/bmad-bmm-check-implementation-readiness
```

## Phase 4 Implementation
Note: Each following workflow in this phase should run a completely new conversation on the Claude Code Chatbot.

Generate a sprint plan
```
/bmad-bmm-sprint-planning
```

Create stories
```
/bmad-bmm-create-story
```

Implement story
```
/bmad-bmm-dev-story
```

Note: When an story is implelented, switch to a different LLM model(i.e. switch to Opus from Sonnet via command /model). Start new Claude Code chat. Then perform code review:
```
/bmad-bmm-code-review
```




