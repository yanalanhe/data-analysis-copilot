# Story 5.3: Template Save & Reuse

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an engineer,
I want to save a successful analysis as a named template and re-apply it to future datasets,
so that I can reuse my best analysis patterns without retyping them each session.

## Acceptance Criteria

1. **Given** a successful analysis has completed, **When** I view the Plan tab, **Then** a "Save as Template" button is visible

2. **Given** I click "Save as Template", **When** I enter a template name and confirm, **Then** the template (plan + code) is written to `templates.json` via `utils/templates.py` and immediately appears in the Template tab list

3. **Given** the Template tab, **When** I open it, **Then** all previously saved templates are listed by name

4. **Given** I select a saved template from the Template tab and click "Apply", **When** the template is loaded, **Then** the template's plan is displayed in the Plan tab and the template's code is loaded into the Code tab editor

5. **Given** the app starts, **When** `init_session_state()` runs, **Then** `load_templates()` from `utils/templates.py` is called and saved templates are loaded into `st.session_state["saved_templates"]` automatically

6. **Given** the subprocess sandbox running generated code, **When** it executes, **Then** it cannot write to `templates.json` — template writes only occur from the UI layer via `utils/templates.py` (NFR9)

## Tasks / Subtasks

- [x] Task 1: Implement `save_template()` in `utils/templates.py` (AC: #2, #6)
  - [x] 1.1: Replace the `raise NotImplementedError` stub in `save_template(name, plan, code)` with full implementation:
    - Load existing templates from `TEMPLATES_FILE` using `load_templates()` (which already handles missing file)
    - Append `{"name": name, "plan": plan, "code": code}` to the list
    - Write the updated list back to `TEMPLATES_FILE` with `json.dump(templates, f, indent=2, ensure_ascii=False)`
    - Keep the function signature unchanged: `save_template(name: str, plan: list[str], code: str) -> None`
  - [x] 1.2: Remove the TODO comment and the docstring line referencing Story 5.3; update docstring to say "Appends a named template to templates.json, creating the file if it does not exist."

- [x] Task 2: Add `show_save_template_form` key to `init_session_state()` in `utils/session.py` (AC: #1, #2)
  - [x] 2.1: Add `"show_save_template_form": False` to the `defaults` dict in `init_session_state()` — this flag controls whether the inline name-entry form is shown in the Plan tab

- [x] Task 3: Add "Save as Template" button and inline save form to the Plan tab in `streamlit_app.py` (AC: #1, #2, #3)
  - [x] 3.1: Add `from utils.templates import save_template` to the imports at the top of `streamlit_app.py`
  - [x] 3.2: In the `with col2row1_plan_tab:` block (around line 1025), after the `else: st.success("✅ Plan approved.")` line, add the Save as Template section:
    ```python
    # Show Save as Template button after a successful run (AC #1)
    if ps and ps.get("execution_success"):
        if not st.session_state.get("show_save_template_form", False):
            if st.button("Save as Template", key="save_template_btn"):
                st.session_state["show_save_template_form"] = True
                st.rerun()
        else:
            # Inline form: text input + confirm/cancel (AC #2)
            template_name = st.text_input(
                "Template name", key="template_name_input", max_chars=80
            )
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("Confirm Save", key="confirm_save_template"):
                    name = template_name.strip()
                    if name:
                        plan_to_save = ps.get("plan", [])
                        code_to_save = ps.get("generated_code", "")
                        save_template(name, plan_to_save, code_to_save)
                        # Reload saved_templates from disk so Template tab reflects new entry
                        from utils.templates import load_templates
                        st.session_state["saved_templates"] = load_templates()
                        st.session_state["show_save_template_form"] = False
                        st.success(f'Template "{name}" saved.')
                        st.rerun()
                    else:
                        st.warning("Enter a name before saving.")
            with col_cancel:
                if st.button("Cancel", key="cancel_save_template"):
                    st.session_state["show_save_template_form"] = False
                    st.rerun()
    ```
    - The `show_save_template_form` flag persists across reruns so the form stays open until the user confirms or cancels
    - `save_template` is only called from the UI layer — never from subprocess (AC #6)

- [x] Task 4: Fix the "Apply" button in the Template tab to actually load plan and code into `pipeline_state` (AC: #4)
  - [x] 4.1: In the `with col2row1_template_tab:` block (around line 1096), replace the current Apply button handler:
    ```python
    # CURRENT (broken - only sets active_template, nothing reads it):
    if st.button("Apply", key=f"apply_tmpl_{idx}_{tmpl.get('name', '')}"):
        st.session_state["active_template"] = tmpl
        st.session_state["active_tab"] = "plan"
        st.rerun()
    ```
    with:
    ```python
    if st.button("Apply", key=f"apply_tmpl_{idx}_{tmpl.get('name', '')}"):
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
        st.session_state["plan_approved"] = False  # Show Execute button in Plan tab
        st.session_state["show_save_template_form"] = False  # Reset form state
        st.rerun()
    ```
    - After rerun: Plan tab reads `pipeline_state["plan"]` → shows template plan + Execute button
    - After rerun: Code tab reads `pipeline_state["generated_code"]` → shows template code in editor

- [x] Task 5: Write tests in `tests/test_template_save_reuse.py` (AC: #2, #3, #4, #5)
  - [x] 5.1: Test `save_template()` with no existing file: creates `templates.json`, returns list with one entry `{"name": "Test", "plan": ["step1"], "code": "import pandas"}`
  - [x] 5.2: Test `save_template()` appends to existing: call twice with different names, verify `load_templates()` returns both in insertion order
  - [x] 5.3: Test `save_template()` with empty plan and empty code: saves without error, loads back with `plan=[]`, `code=""`
  - [x] 5.4: Test `save_template()` preserves unicode in name and code: names with non-ASCII characters are saved and loaded intact
  - [x] 5.5: Test `load_templates()` with non-list JSON in file (e.g., `{}`): returns `[]` (existing behavior, regression guard)
  - [x] 5.6: Test `load_templates()` with file containing valid list: returns the list (regression guard)
  - [x] 5.7: Test that all tests use `tmp_path` fixture (pytest) or `tempfile.TemporaryDirectory` to write to a temp file — **never write to the real `templates.json`**. Patch `utils.templates.TEMPLATES_FILE` to a temp path in each test.

## Dev Notes

### What This Story IS and IS NOT

**IS:**
- Implementing `save_template()` in `utils/templates.py` (replacing the `NotImplementedError` stub)
- Adding a "Save as Template" button to the Plan tab (visible when `execution_success` is True)
- An inline text input + Confirm/Cancel form for naming the template (no modals — UX requirement)
- Reloading `st.session_state["saved_templates"]` from disk immediately after save so the Template tab reflects it without a full page reload
- Fixing the Apply button in the Template tab so it actually loads the template's plan and code into `pipeline_state`

**IS NOT:**
- Changing the subprocess sandbox (NFR9 is already enforced by the existing sandbox — template writes happen in the UI layer, not in subprocess)
- Adding any new files other than `tests/test_template_save_reuse.py`
- Changing `pipeline/` modules — all changes are in `streamlit_app.py`, `utils/templates.py`, `utils/session.py`
- Implementing a "delete template" feature — that is out of scope
- Template editing — users save a new template; they cannot edit existing ones

---

### Current State of `utils/templates.py` (Baseline)

```python
# TEMPLATES_FILE is resolved at module level:
TEMPLATES_FILE = str(Path(__file__).resolve().parent.parent / "templates.json")
# → resolves to: {project-root}/templates.json

def load_templates() -> list[dict]:
    """Load saved templates from templates.json.
    Returns an empty list if the file does not exist or contains invalid data.
    File format: [{"name": str, "plan": list[str], "code": str}]
    """
    if not os.path.exists(TEMPLATES_FILE):
        return []
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return data

def save_template(name: str, plan: list[str], code: str) -> None:
    """Save a named template (plan + code) to templates.json.
    Full implementation in Story 5.3 (template save & reuse).
    """
    # TODO: implement in Story 5.3
    raise NotImplementedError("save_template() implemented in Story 5.3")
```

**Target state after Story 5.3:**
```python
def save_template(name: str, plan: list[str], code: str) -> None:
    """Append a named template (plan + code) to templates.json.
    Creates the file if it does not exist.
    """
    templates = load_templates()
    templates.append({"name": name, "plan": plan, "code": code})
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
```

---

### Current Plan Tab Block (Story 5.2 baseline — lines ~1025–1045)

```python
with col2row1_plan_tab:
    ps = st.session_state.get("pipeline_state")
    plan_steps = ps.get("plan", []) if ps else []
    if plan_steps:
        for i, step in enumerate(plan_steps):
            st.text(f"{i + 1}. {step}")
        if not st.session_state.get("plan_approved", False):
            if st.button("Execute Plan"):
                st.session_state["plan_approved"] = True
                st.session_state["pipeline_running"] = True
                st.rerun()
        else:
            st.success("✅ Plan approved.")
    else:
        st.info("No plan generated yet. Submit a report-type request in the Chat panel.")
```

**After Story 5.3:** The `if plan_steps:` branch gains a section after `st.success("✅ Plan approved.")`:
```python
        else:
            st.success("✅ Plan approved.")
            # — NEW: Show Save as Template section (AC #1, #2) —
            if ps and ps.get("execution_success"):
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
                                save_template(name, ps.get("plan", []), ps.get("generated_code", ""))
                                from utils.templates import load_templates
                                st.session_state["saved_templates"] = load_templates()
                                st.session_state["show_save_template_form"] = False
                                st.success(f'Template "{name}" saved.')
                                st.rerun()
                            else:
                                st.warning("Enter a name before saving.")
                    with col_cancel:
                        if st.button("Cancel", key="cancel_save_template"):
                            st.session_state["show_save_template_form"] = False
                            st.rerun()
```

---

### Current Template Tab Block (Story 5.2 baseline — lines ~1096–1110)

```python
with col2row1_template_tab:
    saved = st.session_state.get("saved_templates", [])
    if not saved:
        st.info("No saved templates yet. Run an analysis and save it from the Plan tab.")
    else:
        for idx, tmpl in enumerate(saved):
            st.write(f"**{tmpl.get('name', 'Unnamed')}**")
            if st.button("Apply", key=f"apply_tmpl_{idx}_{tmpl.get('name', '')}"):
                st.session_state["active_template"] = tmpl
                st.session_state["active_tab"] = "plan"
                st.rerun()
```

**After Story 5.3:** Apply button handler is replaced to actually load the template:
```python
            if st.button("Apply", key=f"apply_tmpl_{idx}_{tmpl.get('name', '')}"):
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
```

---

### Session State Schema Reference

```python
# Keys added/relevant to Story 5.3 (all initialized in init_session_state()):
"saved_templates": list[dict]     # loaded from templates.json on startup; refreshed after save
"active_template": dict | None    # kept for backward compat; no longer the primary apply mechanism
"show_save_template_form": bool   # NEW in 5.3 — True = inline name form is showing in Plan tab
```

AC#5 is already satisfied: `utils/session.py::init_session_state()` calls `_safe_load_templates()` which calls `load_templates()` on startup. No changes needed for this AC.

---

### Key File Locations

| File | Change | Purpose |
|---|---|---|
| `utils/templates.py` | Replace stub body | Implement `save_template()` with `load_templates()` + `json.dump()` |
| `utils/session.py` | Add key to defaults dict | `"show_save_template_form": False` |
| `streamlit_app.py` | Add import | `from utils.templates import save_template` |
| `streamlit_app.py` | Plan tab ~line 1037 | Add "Save as Template" button + inline form after `st.success("✅ Plan approved.")` |
| `streamlit_app.py` | Template tab ~line 1105 | Replace Apply button handler to load template into `pipeline_state` |
| `tests/test_template_save_reuse.py` | New file | Unit tests for save/load and Apply behavior |

---

### Architecture Compliance

- **`templates.json` write path:** Only `save_template()` in `utils/templates.py` writes the file. `save_template()` is only called from `streamlit_app.py` on button click (UI layer). The subprocess sandbox (`pipeline/nodes/executor.py`) runs in a `tempfile.mkdtemp()` temp dir with a restricted environment — it has no access to the app root where `templates.json` lives. [Source: _bmad-output/planning-artifacts/architecture.md#Security]
- **Module boundary:** Changes to `utils/templates.py` and `utils/session.py` are pure Python with no Streamlit imports — `utils/session.py` is the only utils file permitted to import Streamlit. [Source: _bmad-output/planning-artifacts/architecture.md#Architectural-Boundaries]
- **No modal dialogs:** UX requirement is for inline UI only. The "Save as Template" form uses `st.text_input` + buttons inline within the Plan tab — no `st.dialog` or popup. [Source: _bmad-output/planning-artifacts/ux-design-specification.md]
- **Tab state preservation:** After Apply, the Code tab reads `pipeline_state["generated_code"]` which is now set to template code. The `st_ace` editor re-renders with `value=generated_code` on the next rerun, so the editor shows the template code without re-triggering LLM calls. [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting-Concerns]
- **`plan_approved` reset on Apply:** When a template is applied, `plan_approved` is reset to `False` so the Execute button re-appears in the Plan tab. This lets the user run the template against the current dataset. [Source: _bmad-output/planning-artifacts/architecture.md#Frontend-Architecture]
- **`show_save_template_form` key:** Must be added to `init_session_state()` defaults dict so the key is always present after rerun, preventing `KeyError` on `st.session_state.get("show_save_template_form", False)` calls.

---

### Previous Story Intelligence (from Story 5.2)

- **Story 5.2 (done 2026-03-13, 344 tests passing):**
  - `utils/reexec.py` was extracted as a standalone module (imported in `streamlit_app.py` as `from utils.reexec import build_reexec_state`)
  - Pattern established: extract pure-Python helpers to `utils/` for testability without Streamlit import
  - `isinstance(ps, dict)` guard pattern for `pipeline_state` — always use this instead of `ps is not None`
  - `st_ace` returns `None` on first render — always handle with `x if x is not None else fallback`
  - Inline `st.error()` for validation failures; `st.rerun()` for execution results
  - After `st.rerun()`, `_execution_panel()` (the `@st.fragment`) re-renders using `pipeline_state` — no need to set `pipeline_running=True` for render-only reruns
- **Story 5.1 (done):**
  - Code tab: `st_ace` key is `"code_editor"` (not `"code_viewer"` from 5.1 baseline)
  - Template tab structure already exists in lines 1096–1110 — Apply logic is the only broken piece

---

### Git Intelligence (Recent Work)

```
e7391475 Implemented epic-5 Code Transparency  ← Stories 5.1 and 5.2 are done
8a56ca40 Implemented epic-4 Large Data Resilience
60e038e0 Implemented story 3-6-non-blocking-execution-panel-visual-report-rendering
b6352d31 Implemented epic-2
f1db0016 Implemented story 3-3-ast-allowlist-code-validator
```

Epic 5 commit (`e7391475`) includes Stories 5.1 and 5.2. Story 5.3 is the final story in Epic 5.

---

### Testing Pattern (from adjacent stories)

```python
# tests/test_template_save_reuse.py — example pattern
import json, os, pytest
from pathlib import Path

@pytest.fixture
def template_file(tmp_path, monkeypatch):
    """Patch TEMPLATES_FILE to a temp path so tests never touch real templates.json."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)
    return temp_file

def test_save_template_creates_file(template_file):
    from utils.templates import save_template, load_templates
    save_template("My Analysis", ["step1", "step2"], "import pandas as pd")
    assert os.path.exists(template_file)
    loaded = load_templates()
    assert len(loaded) == 1
    assert loaded[0] == {"name": "My Analysis", "plan": ["step1", "step2"], "code": "import pandas as pd"}
```

Test all edge cases: file missing (first save creates it), multiple saves (both load back), empty plan/code, unicode names.

---

### Project Context Reference

- `project-context.md` path: `docs/project-context.md` or `**/project-context.md`
- Architecture module boundary rule: `pipeline/` modules never import `streamlit`; `utils/session.py` is the only utils file that may import `streamlit`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_No debug issues encountered._

### Completion Notes List

- Implemented `save_template(name, plan, code)` in `utils/templates.py`: replaces `NotImplementedError` stub; calls `load_templates()` to read existing list, appends new entry, writes back with `json.dump(..., ensure_ascii=False)` for unicode safety.
- Added `"show_save_template_form": False` to `init_session_state()` defaults dict in `utils/session.py` so the Plan tab inline form state is always present.
- Added `from utils.templates import save_template, load_templates` to `streamlit_app.py` top-level imports.
- Plan tab: "Save as Template" button appears when `execution_success` is True. Clicking toggles `show_save_template_form=True`. Inline form (`st.text_input` + Confirm/Cancel) uses `isinstance(ps, dict)` guard (per 5.2 pattern). On confirm: calls `save_template()`, reloads `saved_templates` from disk immediately, resets form flag, calls `st.rerun()` so Template tab shows new entry (AC #2, #3).
- Template tab Apply button: replaced broken handler (only set `active_template`) with full implementation that writes `pipeline_state["plan"]` and `pipeline_state["generated_code"]` from template data, resets `execution_success=False`/`plan_approved=False`/`show_save_template_form=False`, then `st.rerun()` — Plan tab now shows template plan + Execute button; Code tab shows template code in editor (AC #4).
- Updated `tests/test_story_1_2.py::test_save_template_raises_not_implemented` → `test_save_template_is_callable` since the stub is now fully implemented.
- 8 new tests in `tests/test_template_save_reuse.py`; all use `monkeypatch` to redirect `TEMPLATES_FILE` to `tmp_path` — real `templates.json` never touched.
- Full regression suite: **352 passed, 0 failures** (344 baseline + 8 new).

### File List

- `utils/templates.py` (modified — implemented `save_template()`, updated docstring)
- `utils/session.py` (modified — added `"show_save_template_form": False` to defaults)
- `streamlit_app.py` (modified — added import, Plan tab Save as Template section, Template tab Apply fix)
- `tests/test_template_save_reuse.py` (new — 8 unit tests for save/load)
- `tests/test_story_1_2.py` (modified — updated stub test to callable check)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story status set to review)
- `.gitignore` (modified — added templates.json)

### Change Log

- 2026-03-13: Story 5.3 implemented — `save_template()` fully implemented in `utils/templates.py`; "Save as Template" inline form added to Plan tab; Template tab Apply button fixed to actually load plan+code into `pipeline_state`. 8 new tests, 352 total passing.
- 2026-03-13: Code review fixes — added `templates.json` to `.gitignore` (H1); added `JSONDecodeError`/`OSError` handling in `load_templates()` (H2); wrapped `save_template()` call in try/except (M4); replaced invisible `st.success()` with `st.toast()` (M2); added duplicate template name check (M3); updated File List to include `sprint-status.yaml` (M1).
