# tests/game/test_biomes.py
"""
Tests for server-wide biomes, scheduling, multipliers, and /biome command views.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from systems.core.database import db
from systems.game import biomes
from systems.game.biomes import (
    BIOMES,
    check_and_advance_biome,
    clear_active_biome,
    format_active_biome_banner,
    get_active_biome,
    set_next_biome_timestamp,
    trigger_biome,
)
from systems.bot.commands.biome import BiomeBrowserView, BiomeCommand
from systems.game.raritylist import RARITIES
from systems.game.utils import RARITY_ID_TO_NAME, roll_rarities


@pytest.fixture(autouse=True)
def reset_biome_state():
    clear_active_biome()
    set_next_biome_timestamp(time.time() + 7200)
    yield
    clear_active_biome()


def test_all_biome_rarities_exist_in_raritylist():
    for biome_id, defn in BIOMES.items():
        assert defn["rarities"], f"Biome {biome_id} has no rarities"
        for rid in defn["rarities"]:
            assert rid in RARITY_ID_TO_NAME, (
                f"Biome {biome_id} references unknown rarity ID '{rid}'"
            )


def test_biome_trigger_and_expiration():
    now = 1_700_000_000.0
    state = trigger_biome(biome_id="jotunn_frost", multiplier=5.0, duration_seconds=1200, now=now)
    assert state["id"] == "jotunn_frost"
    assert state["multiplier"] == 5.0
    assert state["ends_at"] == now + 1200
    assert RARITY_ID_TO_NAME["jotunn"] in state["rarity_names"]

    active = get_active_biome(now=now + 600)
    assert active is not None
    assert active["id"] == "jotunn_frost"

    banner = format_active_biome_banner(now=now + 600)
    assert banner is not None
    assert "Jötunn Permafrost" in banner
    assert "x5" in banner
    assert "10m 0s" in banner

    expired = get_active_biome(now=now + 1201)
    assert expired is None


def test_check_and_advance_biome_triggers_when_scheduled():
    now = 1_700_000_000.0
    set_next_biome_timestamp(now + 100)

    assert check_and_advance_biome(now=now + 50) is None
    assert get_active_biome(now=now + 50) is None

    triggered = check_and_advance_biome(now=now + 100)
    assert triggered is not None
    assert 3.0 <= triggered["multiplier"] <= 10.0
    assert 15 * 60 <= triggered["duration_seconds"] <= 30 * 60
    assert get_active_biome(now=now + 100) is not None


@pytest.mark.asyncio
async def test_roll_rarities_applies_biome_multiplier(tmp_path):
    test_db = str(tmp_path / "test_biome_rolls.db")
    old_path = db.db_path
    await db.close()
    db.db_path = test_db
    await db.initialize()

    try:
        trigger_biome(biome_id="the_53_apparition", multiplier=10.0, duration_seconds=900)
        captured_weights = {}

        orig_choices = biomes.random.choices

        def spy_choices(population, weights=None, k=1):
            captured_weights["weights"] = list(weights)
            return orig_choices(population, weights=weights, k=k)

        with patch("systems.game.utils.random.choices", side_effect=spy_choices):
            res = await roll_rarities("user_biome_1", count=5, provided_luck=1.0)
            assert len(res) == 5

        idx_53 = next(i for i, r in enumerate(RARITIES) if r[2] == "53")
        idx_common = next(i for i, r in enumerate(RARITIES) if r[2] == "common")
        assert abs(captured_weights["weights"][idx_53] - (RARITIES[idx_53][1] * 10.0)) < 1e-12
        assert abs(captured_weights["weights"][idx_common] - RARITIES[idx_common][1]) < 1e-12
    finally:
        await db.close()
        db.db_path = old_path


@pytest.mark.asyncio
async def test_biome_command_and_browser():
    bot = MagicMock()
    cog = BiomeCommand(bot)
    inter = MagicMock()
    inter.user.id = 42
    inter.response.send_message = AsyncMock()
    inter.response.edit_message = AsyncMock()

    await cog.biome.callback(cog, inter)
    inter.response.send_message.assert_awaited_once()
    kwargs = inter.response.send_message.call_args.kwargs
    embed = kwargs["embed"]
    view: BiomeBrowserView = kwargs["view"]
    assert "No Biome" in embed.title

    trigger_biome(biome_id="solar_flare", multiplier=7.0, duration_seconds=1800)
    status_embed = view.format_embed()
    assert "Solar Flare" in status_embed.title
    assert any("x7" in f.value for f in status_embed.fields)

    await view.switch_to_browse(inter)
    assert view.mode == "browse"
    inter.response.edit_message.assert_awaited()
