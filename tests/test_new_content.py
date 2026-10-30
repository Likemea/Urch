# Urch/tests/test_new_content.py
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import biomes
from biomes import (
    BIOMES,
    trigger_biome,
    get_active_biome,
    clear_active_biome,
    check_and_advance_biome,
    set_next_biome_timestamp,
    format_active_biome_banner,
)
from recipes import POTION_RECIPES
from buffs import apply_potion_craft, evaluate_active_buffs, apply_dupe_buff
from commands.pit import (
    calculate_sacrifice_qty,
    find_closest_rarity_for_value,
    PitView,
    PitCommand,
    RARITY_NAME_TO_ID,
)
from commands.biome import BiomeCommand, BiomeBrowserView
from utils import (
    ensure_user,
    get_user_data,
    save_user_data,
    roll_rarities,
    process_autorolls,
    RARITY_ID_TO_NAME,
)
from database import db


@pytest.fixture(autouse=True)
def reset_biome_state():
    clear_active_biome()
    set_next_biome_timestamp(time.time() + 7200)
    yield
    clear_active_biome()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Server-Wide Biomes Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_all_biome_rarities_exist_in_raritylist():
    for biome_id, defn in BIOMES.items():
        assert defn["rarities"], f"Biome {biome_id} has no rarities"
        for rid in defn["rarities"]:
            assert rid in RARITY_ID_TO_NAME, f"Biome {biome_id} references unknown rarity ID '{rid}'"


def test_biome_trigger_and_expiration():
    now = 1_700_000_000.0
    state = trigger_biome(biome_id="jotunn_frost", multiplier=5.0, duration_seconds=1200, now=now)
    assert state["id"] == "jotunn_frost"
    assert state["multiplier"] == 5.0
    assert state["ends_at"] == now + 1200
    assert RARITY_ID_TO_NAME["jotunn"] in state["rarity_names"]

    # Active midway through
    active = get_active_biome(now=now + 600)
    assert active is not None
    assert active["id"] == "jotunn_frost"

    banner = format_active_biome_banner(now=now + 600)
    assert banner is not None
    assert "Jötunn Permafrost" in banner
    assert "x5" in banner
    assert "10m 0s" in banner

    # Expired after duration
    expired = get_active_biome(now=now + 1201)
    assert expired is None


def test_check_and_advance_biome_triggers_when_scheduled():
    now = 1_700_000_000.0
    set_next_biome_timestamp(now + 100)

    # Not yet time
    assert check_and_advance_biome(now=now + 50) is None
    assert get_active_biome(now=now + 50) is None

    # Reached scheduled time -> triggers a biome with x3-x10 and 15-30m
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

        with patch("utils.random.choices", side_effect=spy_choices):
            res = await roll_rarities("user_biome_1", count=5, provided_luck=1.0)
            assert len(res) == 5

        from raritylist import RARITIES

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

    # Trigger a biome and refresh status
    trigger_biome(biome_id="solar_flare", multiplier=7.0, duration_seconds=1800)
    status_embed = view.format_embed()
    assert "Solar Flare" in status_embed.title
    assert any("x7" in f.value for f in status_embed.fields)

    # Switch to browse mode
    await view.switch_to_browse(inter)
    assert view.mode == "browse"
    inter.response.edit_message.assert_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dupe Potion Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_dupe_potion_recipe_definition():
    assert "dupe_potion" in POTION_RECIPES
    recipe = POTION_RECIPES["dupe_potion"]
    buff = recipe["buff"]
    assert buff["type"] == "duration"
    assert buff["duration_seconds"] == 300
    assert buff["dupe_chance"] == 0.25
    assert buff["dupe_min_one_in"] == 1_000_000


def test_apply_dupe_buff_only_dupes_1m_plus():
    common_name = RARITY_ID_TO_NAME["common"]  # 1 in 2
    space_name = RARITY_ID_TO_NAME["space"]  # 1 in 999,999
    planetary_name = RARITY_ID_TO_NAME["planetary"]  # 1 in 1,000,000
    galactic_name = RARITY_ID_TO_NAME["galactic"]  # 1 in 10,000,000

    buff_data = {"dupe_chance": 0.25, "dupe_min_one_in": 1_000_000}

    # When random.random() returns 0.10 (< 0.25), only >= 1M rarities duplicate
    with patch("buffs.random.random", return_value=0.10):
        rolls = [common_name, space_name, planetary_name, galactic_name]
        final_rolls, duped = apply_dupe_buff(rolls, buff_data)
        assert final_rolls.count(common_name) == 1
        assert final_rolls.count(space_name) == 1
        assert final_rolls.count(planetary_name) == 2
        assert final_rolls.count(galactic_name) == 2
        assert duped == [planetary_name, galactic_name]

    # When random.random() returns 0.50 (>= 0.25), nothing duplicates
    with patch("buffs.random.random", return_value=0.50):
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

        # Verify autoroll also triggers dupe when dupe_potion is active
        galactic_name = RARITY_ID_TO_NAME["galactic"]
        with (
            patch("utils.roll_rarities", new=AsyncMock(return_value=[galactic_name])),
            patch("buffs.random.random", return_value=0.05),
        ):
            await process_autorolls([uid])

        user = await get_user_data(uid)
        assert user["inventory"].get(galactic_name) == 2
    finally:
        await db.close()
        db.db_path = old_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. The Pit Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_pit_calculate_sacrifice_qty_modes():
    assert calculate_sacrifice_qty(1, "keep_one") == 0
    assert calculate_sacrifice_qty(10, "keep_one") == 9
    assert calculate_sacrifice_qty(10, "all") == 10
    assert calculate_sacrifice_qty(1, "all") == 1
    assert calculate_sacrifice_qty(10, "half") == 5
    assert calculate_sacrifice_qty(1, "half") == 1


def test_pit_100_x_1t_gives_100t_rarity():
    # Sacrificing 100 copies of a 1T rarity (1e12) -> total_value = 100T (1e14) -> Plasmatic (1 in 100T)
    total_value = 100 * 1e12
    match = find_closest_rarity_for_value(total_value)
    assert match is not None
    chosen_name, tier_one_in, tied = match
    assert chosen_name == RARITY_ID_TO_NAME["plasmatic"]
    assert abs(tier_one_in - 1e14) / 1e14 < 1e-6


@pytest.mark.asyncio
async def test_pit_view_interactive_sacrifice_flow(tmp_path):
    test_db = str(tmp_path / "test_pit.db")
    old_path = db.db_path
    await db.close()
    db.db_path = test_db
    await db.initialize()

    try:
        uid = "pit_user_1"
        user = await ensure_user(uid)
        woah_name = RARITY_ID_TO_NAME["woah"]  # 1 in 1T
        plasmatic_name = RARITY_ID_TO_NAME["plasmatic"]  # 1 in 100T
        user["inventory"] = {woah_name: 101}
        user["discovered"] = {woah_name: True}
        await save_user_data(uid, user)

        view = PitView(uid, user["inventory"])
        # Default mode is "keep_one" -> selecting woah sacrifices 100 copies and keeps 1!
        inter = MagicMock()
        inter.user.id = uid
        inter.response.edit_message = AsyncMock()
        inter.response.send_message = AsyncMock()

        await view.on_select_page(inter)
        plan, total_val = view.compute_sacrifice_plan()
        assert len(plan) == 1
        assert plan[0][0] == woah_name
        assert plan[0][1] == 100  # 101 owned - 1 kept = 100 sacrificed
        assert abs(total_val - 1e14) / 1e14 < 1e-6

        await view.on_confirm_sacrifice(inter)

        updated = await get_user_data(uid)
        assert updated["inventory"].get(woah_name) == 1  # 1 kept!
        assert updated["inventory"].get(plasmatic_name) == 1  # 100T rarity forged!
        assert updated["discovered"].get(plasmatic_name) is True
        assert updated["highscore"] == plasmatic_name
    finally:
        await db.close()
        db.db_path = old_path

