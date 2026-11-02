# tests/core/test_config.py
"""
Syntax, package structure, and module import verification across Urch.
"""

import ast
import os
import pathlib
import pytest

URCH_ROOT = pathlib.Path(__file__).resolve().parents[2]


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


@pytest.mark.parametrize(
    "module_name",
    [
        "systems.ai.providers",
        "systems.game.recipes",
        "systems.bot.rate_limiter",
        "systems.core.database",
        "systems.game.buffs",
        "systems.game.utils",
        "systems.ai.agent",
        "systems.ai.functions.tools_schema",
        "systems.ai.functions.dispatcher",
        "systems.ai.functions.audio_gen",
        "systems.ai.functions.forum_post",
    ],
)
def test_core_modules_import(module_name):
    """Importing these modules must not raise."""
    __import__(module_name)


def test_commands_directory_exists():
    cmds_dir = URCH_ROOT / "systems" / "bot" / "commands"
    assert cmds_dir.is_dir(), "systems/bot/commands/ directory is missing"
    py_files = [f for f in os.listdir(cmds_dir) if f.endswith(".py") and f != "__init__.py"]
    assert py_files, "No command modules found in systems/bot/commands/"
