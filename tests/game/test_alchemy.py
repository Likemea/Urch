# tests/game/test_alchemy.py
"""
Tests for potion recipes, multi-crafting, cap enforcement, charge deduction,
and dupe potion buffs.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from systems.core import database as db_mod
from systems.core.database import db
from systems.game import buffs, utils
from systems.game.buffs import apply_dupe_buff, apply_potion_craft, evaluate_active_buffs
from systems.game.recipes import POTION_RECIPES
from systems.game.utils import (
    RARITY_ID_TO_NAME,
    ensure_user,
    get_user_data,
    process_autorolls,
)


def test_potion_recipes_well_formed():
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


def test_recipes_mismatches_resolved():
    """Verifies recipe text matches duration_seconds and charges in recipes.py."""
    med = POTION_RECIPES["medium_luck_potion"]
    assert "3 minutes" in med["description"]
    assert med["buff"]["duration_seconds"] == 180

    large = POTION_RECIPES["large_luck_potion"]
    assert "5 minutes" in large["description"]
    assert large["buff"]["duration_seconds"] == 300

    hyper = POTION_RECIPES["hypercharge_potion"]
    assert "25 manual rolls" in hyper["description"]
    assert hyper["buff"]["charges"] == 25


def test_dupe_potion_recipe_definition():
    assert "dupe_potion" in POTION_RECIPES
    recipe = POTION_RECIPES["dupe_potion"]
    buff = recipe["buff"]
    assert buff["type"] == "duration"
    assert buff["duration_seconds"] == 300
    assert buff["dupe_chance"] == 0.25
    assert buff["dupe_min_one_in"] == 1_000_000


def test_apply_dupe_buff_only_dupes_1m_plus():
    common_name = RARITY_ID_TO_NAME["common"]
    space_name = RARITY_ID_TO_NAME["space"]
    planetary_name = RARITY_ID_TO_NAME["planetary"]
    galactic_name = RARITY_ID_TO_NAME["galactic"]

    buff_data = {"dupe_chance": 0.25, "dupe_min_one_in": 1_000_000}

    with patch("systems.game.buffs.random.random", return_value=0.10):
        rolls = [common_name, space_name, planetary_name, galactic_name]
        final_rolls, duped = apply_dupe_buff(rolls, buff_data)
        assert final_rolls.count(common_name) == 1
        assert final_rolls.count(space_name) == 1
        assert final_rolls.count(planetary_name) == 2
        assert final_rolls.count(galactic_name) == 2
        assert duped == [planetary_name, galactic_name]

    with patch("systems.game.buffs.random.random", return_value=0.50):
        rolls = [planetary_name, galactic_name]
        final_rolls, duped = apply_dupe_buff(rolls, buff_data)
        assert len(final_rolls) == 2
        assert duped == []


@pytest.mark.asyncio
async def test_dupe_potion_craft_and_autoroll_integration(tmp_path):
    test_db = str(tmp_path / "test_dupe_potion.db")
    old_path = db.db_path
    await db.close()
    db.db_path = test_db
    await db.initialize()

    try:
        uid = "dupe_tester_1"
        await ensure_user(uid)
        ok = await apply_potion_craft(uid, "dupe_potion", amount=1)
        assert ok is True

        buff_data = await evaluate_active_buffs(uid, context="manual")
        assert buff_data["dupe_chance"] == 0.25
        assert "🧬 Dupe Potion" in buff_data["active_names"]

        galactic_name = RARITY_ID_TO_NAME["galactic"]
        with (
            patch("systems.game.utils.roll_rarities", new=AsyncMock(return_value=[galactic_name])),
            patch("systems.game.buffs.random.random", return_value=0.05),
        ):
            await process_autorolls([uid])

        user = await get_user_data(uid)
        assert user["inventory"].get(galactic_name) == 2
    finally:
        await db.close()
        db.db_path = old_path


@pytest.mark.asyncio
async def test_buffs_charge_atomic_deduction():
    """Verify evaluate_active_buffs only sets is_active if currency_remove returns True."""
    user_id = 5555

    with patch("systems.game.buffs.currency_count", AsyncMock(return_value=1)):
        with patch("systems.game.buffs.currency_remove", AsyncMock(return_value=False)):
            res = await buffs.evaluate_active_buffs(user_id, context="manual")
            assert res.get("luck_mult", 1.0) == 1.0


@pytest.mark.asyncio
async def test_multi_craft_potions_not_wiped_by_sanitizer(fresh_db, monkeypatch):
    """Verifies legitimate multi-crafted potions survive _sanitize_glitched_potions on restart."""
    monkeypatch.setattr(utils, "db", fresh_db)
    user_id = "potion_crafter"
    await fresh_db.ensure_user(user_id)

    await buffs.apply_potion_craft(user_id, "all_or_nothing_potion", amount=10)
    user = await fresh_db.get_user_data(user_id)
    assert user["currencies"]["potion_charge_all_or_nothing_potion"] == 10

    await buffs.apply_potion_craft(user_id, "overclock_potion", amount=15)
    user = await fresh_db.get_user_data(user_id)
    now = int(datetime.now(timezone.utc).timestamp())
    exp = user["currencies"]["potion_exp_overclock_potion"]
    assert exp >= now + 8900

    await fresh_db._sanitize_glitched_potions()

    user_after = await fresh_db.get_user_data(user_id)
    assert user_after["currencies"]["potion_charge_all_or_nothing_potion"] == 10
    assert user_after["currencies"]["potion_exp_overclock_potion"] >= now + 8900


@pytest.mark.asyncio
async def test_craft_command_exceed_cap_protection(fresh_db, monkeypatch):
    """Verifies that /recipes craft blocks crafting beyond the 24h / 1000 charge cap without consuming items."""
    from systems.bot.commands.alchemy import RecipesCommand

    monkeypatch.setattr(utils, "db", fresh_db)
    monkeypatch.setattr(db_mod, "db", fresh_db)

    bot_mock = MagicMock()
    cmd = RecipesCommand(bot_mock)

    user_id = "999888777"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["currencies"] = {"clovers": 1000000}
    user["inventory"] = {"jackpot": 10000, "lucky": 10000, "unique": 10000, "amazing": 10000}
    await fresh_db.save_user_data(user_id, user)

    mock_interaction = MagicMock()
    mock_interaction.user.id = int(user_id)
    mock_interaction.response.send_message = AsyncMock()

    await cmd.craft.callback(cmd, mock_interaction, recipe_id="all_or_nothing_potion", amount=2000)

    mock_interaction.response.send_message.assert_called_once()
    msg = mock_interaction.response.send_message.call_args[0][0]
    assert "exceeds the 1,000 charge limit" in msg

    user_check = await fresh_db.get_user_data(user_id)
    assert user_check["currencies"]["clovers"] == 1000000
