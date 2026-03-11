# utils/templates.py
"""Template persistence utilities — templates.json read/write.

load_templates() is functional in this story.
save_template() is stubbed for Story 5.3.
"""
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
