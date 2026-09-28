# tests/test_phase1.py
"""
Phase 1 — Initialization.
Verifies the bot can be imported, that registries are self-consistent, and
that no module crashes on import. main.py and register_commands.py are
parsed with `ast` only, since importing them would call `bot.run()`.
"""

import ast
import os
import pathlib
import pytest

URCH_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── 1.1 Syntax check every Python file ────────────────────────────────────────
def test_all_files_parse():
    """Every .py under Urch/ must be syntactically valid."""
    failures = []
    for path in URCH_ROOT.rglob("*.py"):
        if "tests" in path.parts or ".venv" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            failures.append(f"{path.relative_to(URCH_ROOT)}: {e}")
    assert not failures, "Syntax errors:\n" + "\n".join(failures)


# ── 1.2 Import core modules ───────────────────────────────────────────────────
@pytest.mark.parametrize(
    "module_name",
    [
        "providers",
        "recipes",
        "rate_limiter",
        "database",
        "buffs",
        "utils",
        "agent",
        "functions.tools_schema",
        "functions.dispatcher",
    ],
)
def test_core_modules_import(module_name):
    """Importing these modules must not raise."""
    __import__(module_name)


# ── 1.3 Model registry integrity ──────────────────────────────────────────────
REQUIRED_MODEL_FIELDS = {
    "id",
    "disp",
    "provider",
    "vision",
    "reasoning_effort",
    "tools",
    "response_format",
    "routable",
}


def test_models_have_required_fields():
    from providers import MODELS, FALLBACK_MODEL_KEY

    assert FALLBACK_MODEL_KEY in MODELS, "Fallback model key missing from MODELS"

    for key, entry in MODELS.items():
        missing = REQUIRED_MODEL_FIELDS - set(entry)
        assert not missing, f"MODELS['{key}'] missing fields: {missing}"


def test_models_use_known_providers():
    from providers import MODELS, PROVIDERS

    for key, entry in MODELS.items():
        assert entry["provider"] in PROVIDERS, (
            f"MODELS['{key}'] uses unknown provider '{entry['provider']}'"
        )


def test_routable_models_have_router_info():
    from providers import MODELS

    for key, entry in MODELS.items():
        if entry.get("routable"):
            assert entry.get("router_info"), f"Routable model '{key}' has no router_info"


# ── 1.4 Rate limiter ↔ MODELS consistency ─────────────────────────────────────
def test_rate_limiter_tier_models_exist_in_models():
    """Every API ID in a tier list must correspond to some MODELS entry's id."""
    from rate_limiter import DEFAULT_TIER_LIMITS
    from providers import MODELS

    known_ids = {entry["id"] for entry in MODELS.values()}
    unknown = []
    for tier, data in DEFAULT_TIER_LIMITS.items():
        for model_id in data.get("models", []):
            if model_id not in known_ids:
                unknown.append(f"{tier}: {model_id}")

    assert not unknown, "Tier entries reference IDs not present in MODELS:\n  " + "\n  ".join(
        unknown
    )


# ── 1.5 Agent tools schema ────────────────────────────────────────────────────
def test_agent_tools_schema_valid():
    from functions.tools_schema import AGENT_TOOLS

    assert isinstance(AGENT_TOOLS, list) and AGENT_TOOLS
    seen_names = set()
    for tool in AGENT_TOOLS:
        assert tool.get("type") == "function"
        fn = tool["function"]
        assert fn.get("name"), "Tool missing function.name"
        assert fn["name"] not in seen_names, f"Duplicate tool name: {fn['name']}"
        seen_names.add(fn["name"])
        assert fn.get("description"), f"Tool '{fn['name']}' missing description"
        params = fn.get("parameters", {})
        assert params.get("type") == "object", (
            f"Tool '{fn['name']}' parameters.type must be 'object'"
        )
        assert "properties" in params


# ── 1.6 Potion recipes ────────────────────────────────────────────────────────
def test_potion_recipes_well_formed():
    from recipes import POTION_RECIPES

    for pid, recipe in POTION_RECIPES.items():
        assert "name" in recipe, f"{pid} missing name"
        assert "reqs" in recipe and isinstance(recipe["reqs"], dict)
        buff = recipe.get("buff", {})
        assert buff.get("type") in ("charges", "duration"), (
            f"{pid} has invalid buff.type '{buff.get('type')}'"
        )
        assert "targets" in buff and isinstance(buff["targets"], list), (
            f"{pid} missing buff.targets"
        )
        if buff["type"] == "charges":
            assert buff.get("charges", 0) > 0, f"{pid} charge amount must be > 0"
        if buff["type"] == "duration":
            assert buff.get("duration_seconds", 0) > 0, f"{pid} duration_seconds must be > 0"


# ── 1.7 Image model registry ──────────────────────────────────────────────────
def test_image_models_well_formed():
    from providers import IMAGE_MODELS

    for key, entry in IMAGE_MODELS.items():
        assert "id" in entry, f"IMAGE_MODELS['{key}'] missing id"
        assert "disp" in entry, f"IMAGE_MODELS['{key}'] missing disp"


# ── 1.8 commands/ directory exists ────────────────────────────────────────────
def test_commands_directory_exists():
    cmds_dir = URCH_ROOT / "commands"
    assert cmds_dir.is_dir(), "commands/ directory is missing"
    py_files = [f for f in os.listdir(cmds_dir) if f.endswith(".py") and f != "__init__.py"]
    assert py_files, "No command modules found in commands/"
