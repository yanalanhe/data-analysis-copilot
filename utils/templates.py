# utils/templates.py
"""Template persistence utilities — templates.json read/write."""
import json
import os
from pathlib import Path

TEMPLATES_FILE = str(Path(__file__).resolve().parent.parent / "templates.json")


def load_templates() -> list[dict]:
    """Load saved templates from templates.json.

    Returns an empty list if the file does not exist or contains invalid data.
    File format: [{"name": str, "plan": list[str], "code": str}]
    """
    if not os.path.exists(TEMPLATES_FILE):
        return []
    try:
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data


def save_template(name: str, plan: list[str], code: str) -> None:
    """Append a named template (plan + code) to templates.json.

    Creates the file if it does not exist.
    """
    templates = load_templates()
    templates.append({"name": name, "plan": plan, "code": code})
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
