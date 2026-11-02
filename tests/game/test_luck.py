# tests/game/test_luck.py
"""
Tests for luck calculations, exponential bonuses, and /setluck overrides.
"""

import math
from unittest.mock import AsyncMock, MagicMock
import pytest
import discord

from systems.game import utils
from systems.bot.commands.setluck import SetLuckCommand
from systems.game.upgrades import get_upgrade_effect
from systems.game.upgrades.luck_upgrades import LUCK_UPGRADES
from systems.game.raritylist import RARITIES


@pytest.mark.asyncio
async def test_setluck_rejects_nan_inf_and_invalid_negatives(fresh_db):
    bot = MagicMock()
    cmd = SetLuckCommand(bot)

    for bad_val in [float("nan"), float("inf"), float("-inf"), -500.0, -2.0, -0.5]:
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user.id = 111222333
        interaction.response.send_message = AsyncMock()

        await cmd.setluck.callback(cmd, interaction, value=bad_val)
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "❌" in args[0]
        assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_setluck_remove_override_executes_sql_null_update(fresh_db):
    bot = MagicMock()
    cmd = SetLuckCommand(bot)
    user_id = "111222333"

    await fresh_db.ensure_user(user_id)
    user = await fresh_db.get_user_data(user_id)
    user["max_luck"] = 100.0
    user["luck_override"] = 50.0
    await fresh_db.save_user_data(user_id, user)

    check = await fresh_db.get_user_data(user_id)
    assert check["luck_override"] == 50.0

    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = int(user_id)
    interaction.response.send_message = AsyncMock()

    await cmd.setluck.callback(cmd, interaction, value=-1.0)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "removed" in embed.description.lower()

    after = await fresh_db.get_user_data(user_id)
    assert after["luck_override"] is None

    interaction2 = MagicMock(spec=discord.Interaction)
    interaction2.user.id = int(user_id)
    interaction2.response.send_message = AsyncMock()
    await cmd.setluck.callback(cmd, interaction2, value=-1.0)
    embed2 = interaction2.response.send_message.call_args.kwargs["embed"]
    assert "No luck override active" in embed2.description


@pytest.mark.asyncio
async def test_luck_override_is_not_none_check(fresh_db):
    """Verify luck_override=0 is respected and not treated as falsy."""
    await fresh_db.ensure_user(1234)
    user = await fresh_db.get_user_data(1234)
    user["luck_override"] = 0.0
    await fresh_db.save_user_data(1234, user)

    res = await utils.roll_rarities(1234, 1)
    assert len(res) == 1


def test_exp_luck_only_applies_exponential_bonus():
    user_obj = {
        "highscore": RARITIES[10][0],  # idx = 10
        "upgrades": {
            "luck": {"exp_luck": 5},
            "roll": {},
            "clover": {},
        },
    }

    effects = get_upgrade_effect("user_1", user_obj=user_obj, checklist_exp_bonus=1.0)
    assert effects["luck_bonus"] == 0.0

    expected_exp = math.log(12) ** 1.0
    assert math.isclose(effects["exp_bonus"], expected_exp, rel_tol=1e-9)
    assert LUCK_UPGRADES["exp_luck"]["effect"](5, user_obj) == {}
