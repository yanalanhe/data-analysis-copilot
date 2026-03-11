# pipeline/nodes/validator.py
"""AST allowlist code validator node.

Provides two functions:
1. validate_code(code: str) -> tuple[bool, list[str]]
   Pure AST validator — never executes code. Returns (True, []) for valid code
   or (False, [errors]) listing all violations found.

2. validate_code_node(state: PipelineState) -> dict
   Thin LangGraph node wrapper that calls validate_code(), translates errors
   through translate_error(), and returns only changed keys per LangGraph convention.
   This function is wired as the graph node in Story 3.5.

NOTE: Never import streamlit in this file.
"""
import ast

from pipeline.state import PipelineState
from utils.error_translation import AllowlistViolationError, translate_error

# Exact set of permitted top-level module names.
# Includes full dotted names for submodule imports like matplotlib.pyplot.
ALLOWED_IMPORTS = frozenset({
    "pandas",
    "numpy",
    "matplotlib",
    "matplotlib.pyplot",
    "math",
    "statistics",
    "datetime",
    "collections",
    "itertools",
    "io",
    "base64",
})

# Blocked function/attribute names when called as bare names.
BLOCKED_CALLS = frozenset({"eval", "exec", "__import__", "open"})

# Blocked top-level namespace identifiers for attribute access calls (e.g., os.system()).
BLOCKED_NAMESPACES = frozenset({"os", "sys", "subprocess", "socket", "urllib", "requests"})


def _get_root_name(node: ast.expr) -> str | None:
    """Walk an attribute chain to find the root Name identifier.

    Examples:
        ast.Name('os')                  → 'os'
        ast.Attribute(Name('os'), 'path')  → 'os'
        ast.Attribute(Attribute(Name('urllib'), 'request'), 'urlopen')  → 'urllib'
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _get_root_name(node.value)
    return None


def validate_code(code: str) -> tuple[bool, list[str]]:
    """Validate generated code for syntax errors and unsafe operations.

    Uses Python ast module to parse and walk the code AST — never executes the code.

    Returns:
        (True, []) if the code is valid.
        (False, [error_messages]) listing ALL violations found (not just the first).
    """
    # Step 1: Syntax check — if this fails there is no tree to walk.
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    # Step 2: Pre-collect ast.Attribute nodes that serve as func in ast.Call nodes
    # (including chained attrs like urllib.request.urlopen) so we can detect
    # bare attribute *access* on blocked namespaces (e.g. f = os.system) without
    # double-reporting the same node when it also participates in a call check.
    call_func_attr_ids: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            func = n.func
            while isinstance(func, ast.Attribute):
                call_func_attr_ids.add(id(func))
                func = func.value

    errors: list[str] = []

    # Step 3: Walk the full AST and collect all violations.
    for node in ast.walk(tree):

        # --- Import checks ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name  # e.g. "os", "matplotlib.pyplot"
                root = name.split(".")[0]  # e.g. "os", "matplotlib"
                if name not in ALLOWED_IMPORTS and root not in ALLOWED_IMPORTS:
                    errors.append(
                        f"Blocked import: '{name}'. Only these imports are allowed: "
                        + ", ".join(sorted(ALLOWED_IMPORTS))
                    )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if module not in ALLOWED_IMPORTS and root not in ALLOWED_IMPORTS:
                errors.append(
                    f"Blocked import: 'from {module} import ...'. Only these imports are allowed: "
                    + ", ".join(sorted(ALLOWED_IMPORTS))
                )

        # --- Blocked call checks ---
        elif isinstance(node, ast.Call):
            # Bare calls: eval(), exec(), __import__(), open()
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                errors.append(
                    f"Blocked operation: '{node.func.id}()' is not permitted."
                )
            # Attribute calls on blocked namespaces: os.system(), sys.exit(),
            # urllib.request.urlopen(), etc. — walk up the attribute chain to the root Name.
            elif isinstance(node.func, ast.Attribute):
                root_name = _get_root_name(node.func.value)
                if root_name and root_name in BLOCKED_NAMESPACES:
                    errors.append(
                        f"Blocked operation: '{root_name}.{node.func.attr}()' is not permitted."
                    )

        # --- Bare attribute access on blocked namespaces (non-call) ---
        # Catches reference-then-call bypasses: f = os.system; f('ls')
        elif isinstance(node, ast.Attribute) and id(node) not in call_func_attr_ids:
            root_name = _get_root_name(node)
            if root_name and root_name in BLOCKED_NAMESPACES:
                errors.append(
                    f"Blocked operation: '{root_name}.{node.attr}' attribute access is not permitted."
                )

    if errors:
        return False, errors
    return True, []


def validate_code_node(state: PipelineState) -> dict:
    """LangGraph node wrapper for validate_code.

    Calls validate_code() on state['generated_code'], translates any errors
    through translate_error(), and returns only changed keys per LangGraph convention.

    On success: returns {"validation_errors": []}
    On failure: returns {"validation_errors": errors, "execution_success": False,
                          "error_messages": existing + [translated_error]}
    """
    code = state.get("generated_code", "")
    is_valid, errors = validate_code(code)

    if not is_valid:
        translated_errors = []
        for err in errors:
            if err.startswith("Syntax error:"):
                translated = translate_error(SyntaxError(err))
            else:
                translated = translate_error(AllowlistViolationError(err))
            translated_errors.append(translated)

        existing_errors = list(state.get("error_messages", []))
        return {
            "validation_errors": errors,
            "execution_success": False,
            "error_messages": existing_errors + translated_errors,
        }

    return {"validation_errors": []}
