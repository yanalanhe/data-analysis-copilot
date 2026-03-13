"""Tests for template save & reuse (Story 5.3).

Tests cover:
- save_template() creates file and appends entries
- load_templates() regression guards
- Template structure validation
- Unicode handling

All tests use monkeypatch to redirect TEMPLATES_FILE to a temp path — never
touches the real templates.json in the project root.
"""
import json
import os
import pytest


@pytest.fixture(autouse=True)
def patch_templates_file(tmp_path, monkeypatch):
    """Redirect TEMPLATES_FILE to a temp path for every test."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)
    return temp_file


# ---------------------------------------------------------------------------
# Task 1 tests: save_template() implementation
# ---------------------------------------------------------------------------


def test_save_template_creates_file(tmp_path, monkeypatch):
    """5.1 — save_template writes templates.json; load_templates returns one entry."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    from utils.templates import save_template, load_templates

    save_template("My Analysis", ["step1", "step2"], "import pandas as pd")

    assert os.path.exists(temp_file)
    loaded = load_templates()
    assert len(loaded) == 1
    assert loaded[0] == {
        "name": "My Analysis",
        "plan": ["step1", "step2"],
        "code": "import pandas as pd",
    }


def test_save_template_appends_to_existing(tmp_path, monkeypatch):
    """5.2 — Calling save_template twice produces two entries in insertion order."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    from utils.templates import save_template, load_templates

    save_template("First", ["step A"], "code_a = 1")
    save_template("Second", ["step B", "step C"], "code_b = 2")

    loaded = load_templates()
    assert len(loaded) == 2
    assert loaded[0]["name"] == "First"
    assert loaded[1]["name"] == "Second"
    assert loaded[1]["plan"] == ["step B", "step C"]


def test_save_template_empty_plan_and_code(tmp_path, monkeypatch):
    """5.3 — save_template accepts empty plan list and empty code string."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    from utils.templates import save_template, load_templates

    save_template("Empty Template", [], "")

    loaded = load_templates()
    assert len(loaded) == 1
    assert loaded[0]["plan"] == []
    assert loaded[0]["code"] == ""


def test_save_template_preserves_unicode(tmp_path, monkeypatch):
    """5.4 — Unicode characters in name and code are saved and loaded intact."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    from utils.templates import save_template, load_templates

    name = "Análisis de datos — résumé 数据分析"
    code = "# Données: α β γ\nimport pandas as pd"
    save_template(name, ["étape 1", "шаг 2"], code)

    loaded = load_templates()
    assert loaded[0]["name"] == name
    assert loaded[0]["plan"] == ["étape 1", "шаг 2"]
    assert loaded[0]["code"] == code


# ---------------------------------------------------------------------------
# Regression guards for load_templates() (existing behaviour)
# ---------------------------------------------------------------------------


def test_load_templates_missing_file_returns_empty(tmp_path, monkeypatch):
    """5.5 — load_templates returns [] when templates.json does not exist."""
    temp_file = str(tmp_path / "does_not_exist.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    from utils.templates import load_templates

    assert load_templates() == []


def test_load_templates_non_list_json_returns_empty(tmp_path, monkeypatch):
    """5.5 — load_templates returns [] when file contains non-list JSON (e.g. {})."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump({"not": "a list"}, f)

    from utils.templates import load_templates

    assert load_templates() == []


def test_load_templates_valid_list_returns_list(tmp_path, monkeypatch):
    """5.6 — load_templates returns the list when file contains a valid JSON array."""
    temp_file = str(tmp_path / "templates.json")
    monkeypatch.setattr("utils.templates.TEMPLATES_FILE", temp_file)

    data = [{"name": "Saved", "plan": ["x"], "code": "print('hi')"}]
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    from utils.templates import load_templates

    loaded = load_templates()
    assert loaded == data


def test_save_template_no_streamlit_import():
    """5.7 / architecture compliance — utils/templates.py must NOT import streamlit."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "utils" / "templates.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                assert not name.startswith("streamlit"), (
                    "utils/templates.py must not import streamlit"
                )
