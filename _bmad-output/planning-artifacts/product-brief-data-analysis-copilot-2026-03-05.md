---
stepsCompleted: [step-01-init, step-02-vision, step-03-users, step-04-metrics, step-05-scope, step-06-complete]
inputDocuments: []
date: 2026-03-05
author: Yan
---

# Product Brief: data-analysis-copilot

<!-- Content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

The Data Analysis Copilot is a general-purpose AI-powered data analysis assistant built for professionals who need fast, accurate insights from tabular data — without requiring programming expertise. The product's primary validated use case is circuit board fault analysis for enterprise electronics engineers, where it has demonstrated a 70% reduction in analysis time for common problem patterns.

By combining a natural language chat interface with a self-correcting LangGraph execution pipeline, the copilot transforms complex, multi-step data analysis into a conversational experience: upload CSV data, ask a question, review the AI-generated plan, and receive a visual report — all without writing a single line of code.

---

## Core Vision

### Problem Statement

Enterprise electronics engineers spend significant time manually reviewing large volumes of tabular test data (historically managed in Excel) to identify and diagnose circuit board faults. The troubleshooting workflow is complex, repetitive, and inefficient — requiring deep familiarity with the data structure and considerable manual effort to produce actionable analysis.

### Problem Impact

- Engineers lose hours per diagnostic cycle to manual data review
- Excel-based workflows are error-prone, hard to repeat, and non-collaborative
- Fault identification delays increase rework costs and slow production throughput
- The process is a bottleneck that scales poorly as board complexity grows

### Why Existing Solutions Fall Short

Excel, the current dominant tool, requires engineers to manually write formulas, build charts, and interpret patterns — skills orthogonal to their core engineering expertise. There are no purpose-built AI tools that allow engineers to interrogate tabular circuit board data through natural language, plan the analysis automatically, and generate visual reports without code.

### Proposed Solution

The Data Analysis Copilot provides a four-panel Streamlit interface:

- **Chatbot panel** — Natural language queries drive the entire analysis workflow
- **Plan/Code sidebar** — AI generates a step-by-step execution plan, with full code transparency and editability
- **Editable data table** — Engineers upload or paste CSV data and interact with it directly
- **AI-generated report panel** — Visual charts and summaries are rendered automatically from AI-generated Python code

A LangGraph state machine orchestrates the backend: classifying intent, writing Python analysis code, validating and executing it in an isolated subprocess, self-correcting on failure (up to 3 retries), and replanning if code consistently fails — producing reliable reports without requiring manual debugging.

### Key Differentiators

- **70% faster analysis** for common fault patterns compared to Excel-based workflows
- **No coding required** — natural language replaces Python/formula expertise
- **Self-correcting execution** — LangGraph retry + replan loop ensures robust results even when initial code generation fails
- **Full transparency** — engineers can inspect, edit, and rerun the generated code at any time
- **General-purpose** — designed as a universal data analysis copilot that excels in circuit board diagnostics but works across any CSV-based domain
- **LangSmith observability** — full traceability of all LLM calls and agent decisions for debugging and improvement

---

## Target Users

### Primary Users

**Persona: Sam — Electronics Test & Failure Analysis Engineer**

Sam is an enterprise electronics engineer spanning roles across test engineering, failure analysis, and quality control. She's comfortable with Excel and CSV data but is not a programmer. After a test run, she typically has multiple CSV files (voltage, current, time) and needs to turn them into a structured analysis report — a process that currently takes hours in Excel.

**Context & Environment:**
- Works across factory floor, R&D lab, or quality control environments
- Produces and works with tabular test output data (CSV) from test equipment
- Time pressure is constant — faulty boards delay production and increase rework cost
- Primary deliverable: a readable report with charts and trend analysis that she or her manager can act on

**"Aha!" Moment:**
When Sam finds a fault pattern faster than expected — a report that would have taken 2 hours in Excel is ready in 15 minutes — and the tool understood her natural language request without any manual configuration.

---

### Secondary Users

**Persona: Morgan — Engineering Director / Quality Manager**

Morgan oversees teams of engineers and is accountable for production quality metrics, yield rates, and fault trends. Morgan doesn't perform hands-on analysis but reviews the reports and findings that Sam produces. Morgan benefits indirectly from faster fault identification (fewer delays, lower rework costs, better trend visibility) and may influence adoption decisions.

---

### User Journeys

#### Journey 1: Primary User — Success Path

**Opening scene:** Sam has just finished a circuit test run and has three CSVs (voltage, current, time). She used to spend hours in Excel building charts and writing up trends. She wants a report in minutes, not hours.

**Rising action:** She opens the locally hosted app, uploads the three CSVs, then types in natural language: "Report with voltage vs time and current vs time, as well as analyzing the trends." She reviews the plan the system generates and clicks Execute.

**Climax:** The LangGraph agents run, generate the analysis and charts, and assemble the report. The UI displays two charts (voltage vs time, current vs time) and a written trend analysis. She can read and act on it immediately.

**Resolution:** Sam gets a complete analysis report in ~15 minutes instead of ~2 hours. The product understood her intent and delivered without any manual chart-building. She feels confident sharing it directly with Morgan.

---

#### Journey 2: Primary User — Edge Case (Large Data)

**Opening scene:** Sam has a test run that produced very large CSVs (high sample rate, long capture duration). She uploads them and asks for the same kind of report.

**Rising action:** She uploads the files and hits Execute. The system runs but struggles — graphs are slow, unreadable (too many data points), or the run times out. The product doesn't handle the scale gracefully.

**Climax:** Instead of failing silently, the system surfaces the problem clearly: a message that the dataset is large, that visualization may be degraded, and a suggestion to downsample, summarize, or reduce the data.

**Resolution:** Sam can recover through one or more paths (to be resolved in design):
- **(a)** The system automatically downsamples or summarizes for visualization and still produces a usable report
- **(b)** The system suggests "use a subset" or "reduce rows" and she filters the data and retries
- **(c)** She receives a clear warning upfront so she can split or reduce the data before running

**Key requirement:** The product must never leave Sam stuck with a silent failure when the data is very large. Graceful degradation and clear guidance are essential.

---

## Success Metrics

### User Success

**Time-to-report:**
Engineers achieve report creation in ~15 minutes for a typical batch dataset, compared to ~2 hours with Excel. This is the primary user success benchmark.

**Charts without manual grind:**
Users can get to "the right chart" quickly — the system handles the mechanics (data → analysis → graph) while the engineer stays in control of what's being analyzed and why. No formula-writing, no manual chart-building.

**"Aha!" Moment:**
Using natural language to describe what they want (e.g. "create a report with charts for voltage vs time and current vs time") and receiving a concrete plan followed by a report with charts — without writing code or building charts by hand.

---

### Business Objectives

**Internal validation:**
The product can generate a simple report with internal testers, running reliably on local machines.

**Proof point — "This is working":**
Internal testers successfully complete at least one end-to-end run on their own machines:
> Upload CSV → Natural language query → Plan generated → Report with charts displayed

This milestone defines the product as viable for the next phase of development or client demonstration.

---

### Key Performance Indicators

| KPI | Target | Measurement |
|---|---|---|
| Report creation time | ≤ 15 minutes for a typical batch | Timed from CSV upload to rendered report |
| End-to-end success rate | Internal testers complete full flow independently | Manual verification during internal testing |
| Core flow reliability | No flaky runs on the standard workflow (locally hosted) | Repeated test runs on internal machines |
| Natural language → report fidelity | Output matches stated request (correct chart types, correct axes) | Internal tester review of output quality |
| Large data handling | No silent failures; clear guidance surfaced when data is too large | Edge case testing with large CSVs |

---

### Technical Success Criteria

- **Execution model:** User triggers execution (click); agents run autonomously and the report appears in the frontend — no manual debugging required
- **Local reliability:** Stable, repeatable runs on locally hosted instances
- **Graceful degradation:** Large datasets surface a clear message with recovery options rather than failing silently
- **Self-correction:** The LangGraph retry loop resolves code failures without user intervention for the majority of standard requests

---

## MVP Scope

### Core Features (In Scope)

The MVP formalizes and stabilizes the existing implemented functionality, with one key addition and one blocking quality requirement:

**Data Input:**
- Upload multiple CSV files in a single session (e.g. voltage, current, time CSVs)
- Editable data table — paste or load CSV data directly in the browser
- Data persisted in session state and passed as context to all analysis operations

**Analysis Interface:**
- Natural language chat interface for submitting analysis requests
- AI-generated step-by-step execution plan displayed before running
- "Execute Plan" trigger — user-initiated, not automatic
- Smart intent classification (report generation vs. simple Q&A vs. general chat)

**Report Generation:**
- Automated Python code generation from the execution plan
- Code validation: syntax check, security check, LLM logic review
- Subprocess execution in isolated environment (safe, sandboxed)
- Self-correcting execution: up to 3 code retry attempts + adaptive replanning
- Visual report rendered in the AI-generated report panel (charts + trend analysis)
- Editable code viewer — engineers can inspect and modify generated code

**Observability:**
- LangSmith tracing (optional) for debugging LLM calls and agent workflows

**Large Data Handling (Blocking MVP Requirement):**
- Graceful degradation when dataset size causes slow or unreadable visualizations
- Clear user-facing message when data is too large to render effectively
- At least one recovery path: automatic downsampling, or a prompt to reduce/subset the data before retrying
- No silent failures — the system must always communicate what went wrong

---

### Out of Scope for MVP

- **Report export** — PDF, PNG, or file download; "visible in the UI" is sufficient for MVP validation
- **Persistent sessions** — no save/load of sessions or reports across browser refreshes
- **User authentication / multi-user** — single-user local app only
- **Batch processing** — analyzing multiple board datasets sequentially without user interaction
- **Cloud deployment** — MVP is locally hosted only
- **Domain expansion** — the product is scoped to circuit board data analysis; no generalization to other industries in MVP

---

### MVP Success Gate

The MVP is complete when internal testers can independently:
1. Upload multiple CSVs from a real circuit board test run
2. Submit a natural language analysis request
3. Review and execute the generated plan
4. Receive a visual report with correct charts and trend analysis in ≤ 15 minutes
5. Encounter a graceful, actionable message (not a silent failure) when large data is uploaded

---

### Future Vision

The product remains focused on circuit board data analysis. Post-MVP enhancements may include:
- Improved large data handling (streaming, chunked analysis, automatic downsampling)
- Report export (PDF/PNG download)
- Session persistence (save and reload analysis sessions)
- Enhanced visualization options (more chart types, comparison views)
- Support for additional test data formats beyond CSV
- Team-level features (shared sessions, report history)
