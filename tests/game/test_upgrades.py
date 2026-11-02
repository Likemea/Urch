# tests/game/test_upgrades.py
"""
Tests for upgrade definitions, deepened upgrade tiers, requirement resolution,
and upgrade deduction persistence.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from systems.game import utils
from systems.game.upgrades import UPGRADE_CATEGORIES, get_upgrade_effect
from systems.game.upgrades.luck_upgrades import LUCK_UPGRADES
from systems.game.upgrades.clover_upgrades import CLOVER_UPGRADES
from systems.game.raritylist import RARITIES
from systems.game.utils import resolve_item_key

VALID_RARITY_IDS = {r[2] for r in RARITIES}


def test_additive_luck_2_deepened():
    upg = LUCK_UPGRADES["additive_luck_2"]
    assert upg["max_tier"] == 20
    assert len(upg["requirements"]) == 20
    for tier in range(1, 21):
        assert tier in upg["requirements"]
        for item, count in upg["requirements"][tier].items():
            assert count > 0
            key, cat = resolve_item_key(item)
            assert cat in ("inventory", "currency")
            if cat == "inventory":
                assert key in VALID_RARITY_IDS or item in VALID_RARITY_IDS


def test_exp_luck_deepened():
    upg = LUCK_UPGRADES["exp_luck"]
    assert upg["max_tier"] == 18
    assert len(upg["requirements"]) == 18
    for tier in range(1, 19):
        assert tier in upg["requirements"]
        for item, count in upg["requirements"][tier].items():
            assert count > 0
            key, cat = resolve_item_key(item)
            assert cat in ("inventory", "currency")
            if cat == "inventory":
                assert key in VALID_RARITY_IDS or item in VALID_RARITY_IDS


def test_clover_luck_deepened():
    upg = CLOVER_UPGRADES["clover_luck"]
    assert upg["max_tier"] == 20
    assert len(upg["requirements"]) == 20
    for tier in range(1, 21):
        assert tier in upg["requirements"]
        for item, count in upg["requirements"][tier].items():
            assert count > 0
            key, cat = resolve_item_key(item)
            assert cat in ("inventory", "currency")
            if cat == "inventory":
                assert key in VALID_RARITY_IDS or item in VALID_RARITY_IDS


def test_max_deepened_upgrades_effects():
    knowledge_display_name = [r[0] for r in RARITIES if r[2] == "knowledge"][0]
    user = {
        "highscore": knowledge_display_name,
        "upgrades": {
            "luck": {
                "additive_luck_2": 20,
                "exp_luck": 18,
            },
            "clover": {
                "clover_luck": 20,
            },
        },
    }
    effects = get_upgrade_effect("123", user_obj=user)
    assert effects["luck_bonus"] >= 7680
    assert effects["exp_bonus"] > 500.0


@pytest.mark.asyncio
async def test_upgrade_persists_deduction(fresh_db, monkeypatch):
    """Verifies that purchasing an upgrade deducts currencies/items and persists the new tier."""
    monkeypatch.setattr(utils, "db", fresh_db)
    import systems.bot.commands.upgrades as upgrades_mod

    monkeypatch.setattr(upgrades_mod, "ensure_user", utils.ensure_user)
    monkeypatch.setattr(upgrades_mod, "save_user_data", utils.save_user_data)
    monkeypatch.setattr(upgrades_mod, "consume_requirements", utils.consume_requirements)
    monkeypatch.setattr(upgrades_mod, "has_requirements", utils.has_requirements)

    user_id = "123456789"
    await fresh_db.ensure_user(user_id)

    db_lucky, _ = utils.resolve_item_key("lucky")
    user = await fresh_db.get_user_data(user_id)
    user["currencies"] = {"clovers": 20}
    user["inventory"] = {db_lucky: 10}
    await fresh_db.save_user_data(user_id, user)

    from systems.bot.commands.upgrades import UpgradeView

    view = UpgradeView(user_id)
    view.category = "clover"
    keys = list(UPGRADE_CATEGORIES["clover"].keys())
    view.page = keys.index("clover_gain")

    mock_interaction = MagicMock()
    mock_interaction.user.id = int(user_id)
    mock_interaction.response.send_message = AsyncMock()
    mock_interaction.response.edit_message = AsyncMock()

    await view.upgrade.callback(mock_interaction)

    updated = await fresh_db.get_user_data(user_id)
    assert updated["currencies"]["clovers"] == 10
    assert updated["inventory"][db_lucky] == 6
    assert updated["upgrades"]["clover"]["clover_gain"] == 1
