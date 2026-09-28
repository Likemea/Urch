# tests/test_phase3_commands.py
"""
Phase 3 — Commandry.
Loads every command module into a fresh commands.Bot and verifies that
setup(bot) succeeds and that no two modules declare the same command name.
"""

import os
import pathlib
import pytest
import discord
from discord.ext import commands

URCH_ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMANDS_DIR = URCH_ROOT / "commands"


def _command_modules():
    if not COMMANDS_DIR.is_dir():
        return []
    return sorted(
        f"commands.{f[:-3]}"
        for f in os.listdir(COMMANDS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    )


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.reactions = True
    return commands.Bot(command_prefix="!", intents=intents)


# ── 3.1 Every command module has a `setup` ───────────────────────────────────
@pytest.mark.parametrize("mod", _command_modules())
def test_command_module_has_setup(mod):
    module = __import__(mod, fromlist=["setup"])
    assert hasattr(module, "setup"), f"{mod} has no setup(bot) function"
    assert callable(module.setup), f"{mod}.setup is not callable"


# ── 3.2 Every module loads cleanly into a bot ────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("mod", _command_modules())
async def test_command_module_loads(bot, mod):
    """Loading the extension must not raise. If this fails, the whole bot
    will silently lose that cog at startup."""
    try:
        await bot.load_extension(mod)
    except Exception as e:
        pytest.fail(f"Failed to load {mod}: {type(e).__name__}: {e}")


# ── 3.3 All commands together load ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_all_commands_load_together(bot):
    """Cross-module conflicts (duplicate names, shared state) often only appear
    when everything is loaded at once."""
    errors = []
    for mod in _command_modules():
        try:
            await bot.load_extension(mod)
        except Exception as e:
            errors.append(f"{mod}: {type(e).__name__}: {e}")
    assert not errors, "Load failures:\n  " + "\n  ".join(errors)


# ── 3.4 No duplicate slash-command names ─────────────────────────────────────
@pytest.mark.asyncio
async def test_no_duplicate_slash_command_names(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    names = [cmd.name for cmd in bot.tree.get_commands()]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate slash-command names: {duplicates}"


# ── 3.5 No duplicate prefix-command names ────────────────────────────────────
@pytest.mark.asyncio
async def test_no_duplicate_prefix_command_names(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    names = list(bot.commands.keys())
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate prefix-command names: {duplicates}"


# ── 3.6 Slash commands have descriptions ─────────────────────────────────────
@pytest.mark.asyncio
async def test_slash_commands_have_descriptions(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    missing = [
        cmd.qualified_name
        for cmd in bot.tree.get_commands()
        if not getattr(cmd, "description", None)
    ]
    assert not missing, f"Slash commands missing descriptions: {missing}"
