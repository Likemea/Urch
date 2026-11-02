# tests/game/test_pit.py
"""
Tests for The Pit sacrifice mechanics, value matching, Pit Luck divisor curve,
and PitView interactive flows.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
import pytest

from systems.core.database import db
from systems.game.raritylist import RARITIES
from systems.game.upgrades.luck_upgrades import LUCK_UPGRADES, get_pit_luck_divisor
from systems.game.upgrades import get_upgrade_effect
from systems.bot.commands.pit import (
    PitView,
    calculate_sacrifice_qty,
    find_closest_rarity_for_value,
)
from systems.game.utils import ensure_user, get_user_data, save_user_data, RARITY_ID_TO_NAME

RARITY_DICT = {r[2]: r[0] for r in RARITIES}
RARITY_VALS = {r[2]: (1.0 / r[1]) if r[1] > 0 else 0.0 for r in RARITIES}


def test_pit_calculate_sacrifice_qty_modes():
    assert calculate_sacrifice_qty(1, "keep_one") == 0
    assert calculate_sacrifice_qty(10, "keep_one") == 9
    assert calculate_sacrifice_qty(10, "all") == 10
    assert calculate_sacrifice_qty(1, "all") == 1
    assert calculate_sacrifice_qty(10, "half") == 5
    assert calculate_sacrifice_qty(1, "half") == 1


def test_pit_100_x_1t_gives_100t_rarity():
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
        inter = MagicMock()
        inter.user.id = uid
        inter.response.edit_message = AsyncMock()
        inter.response.send_message = AsyncMock()

        await view.on_select_page(inter)
        plan, total_val = view.compute_sacrifice_plan()
        assert len(plan) == 1
        assert plan[0][0] == woah_name
        assert plan[0][1] == 100
        assert abs(total_val - 1e14) / 1e14 < 1e-6

        await view.on_confirm_sacrifice(inter)

        updated = await get_user_data(uid)
        assert updated["inventory"].get(woah_name) == 1
        assert updated["inventory"].get(plasmatic_name) == 1
        assert updated["discovered"].get(plasmatic_name) is True
        assert updated["highscore"] == plasmatic_name
    finally:
        await db.close()
        db.db_path = old_path


def test_pit_luck_divisor_curve():
    assert pytest.approx(get_pit_luck_divisor(1), rel=1e-5) == 1_000_000.0
    assert pytest.approx(get_pit_luck_divisor(20), rel=1e-5) == 1_000.0

    divisors = [get_pit_luck_divisor(t) for t in range(1, 21)]
    for i in range(len(divisors) - 1):
        assert divisors[i] > divisors[i + 1]

    assert pytest.approx(get_pit_luck_divisor(0), rel=1e-5) == 1_000_000.0
    assert pytest.approx(get_pit_luck_divisor(-5), rel=1e-5) == 1_000_000.0
    assert pytest.approx(get_pit_luck_divisor(25), rel=1e-5) == 1_000.0


def test_pit_luck_requirements_and_difficulty():
    upg = LUCK_UPGRADES.get("pit_luck")
    assert upg is not None
    assert upg["max_tier"] == 20
    reqs = upg["requirements"]
    assert len(reqs) == 20

    prev_diff = 0
    for tier in range(1, 21):
        assert tier in reqs
        tier_req = reqs[tier]
        assert len(tier_req) > 0

        for rid, count in tier_req.items():
            assert rid in RARITY_DICT, f"Invalid rarity ID: {rid} in tier {tier}"
            assert count > 0

        diff = sum(RARITY_VALS[rid] * count for rid, count in tier_req.items())
        assert diff > prev_diff, (
            f"Tier {tier} difficulty ({diff}) did not increase over Tier {tier - 1} ({prev_diff})"
        )
        prev_diff = diff

    t1_diff = sum(RARITY_VALS[r] * c for r, c in reqs[1].items())
    assert 1_000_000 <= t1_diff <= 2_500_000

    t20_diff = sum(RARITY_VALS[r] * c for r, c in reqs[20].items())
    assert 10**21 <= t20_diff <= 3.5 * 10**21


def test_pit_luck_effect_in_upgrade_system():
    user = {
        "upgrades": {"luck": {"pit_luck": 0}},
        "pit_luck": 500.0,
    }
    eff0 = get_upgrade_effect("user1", user)
    assert eff0["luck_bonus"] == 0.0

    user["upgrades"]["luck"]["pit_luck"] = 1
    eff1 = get_upgrade_effect("user1", user)
    assert eff1["luck_bonus"] == 500.0

    user["pit_luck"] = 12500.5
    eff2 = get_upgrade_effect("user1", user)
    assert eff2["luck_bonus"] == 12500.5


@pytest.mark.asyncio
async def test_pit_view_embed_preview():
    exode_name = RARITY_DICT["exode"]
    inventory = {exode_name: 5}
    view = PitView("user1", inventory, pit_tier=0, pit_luck=0.0)
    embed = view.format_embed()
    assert "Pit Luck" not in (embed.footer.text or "")

    view_with_tier = PitView("user1", inventory, pit_tier=5, pit_luck=42.0)
    embed_with_tier = view_with_tier.format_embed()
    assert "Pit Luck: T5" in (embed_with_tier.footer.text or "")

    view_with_tier.selected_ids.add("exode")
    embed_preview = view_with_tier.format_embed()
    field_names = [f.name for f in embed_preview.fields]
    assert "🍀 Pit Luck" in field_names


@pytest.mark.asyncio
async def test_pit_sacrifice_awards_luck(monkeypatch):
    from systems.core import database

    exode_name = RARITY_DICT["exode"]
    fake_user = {
        "inventory": {exode_name: 10},
        "discovered": {exode_name: True},
        "upgrades": {"luck": {"pit_luck": 1}},
        "pit_luck": 10.0,
        "highscore": exode_name,
    }

    async def mock_ensure_user(user_id):
        return fake_user

    async def mock_save_user_data(user_id, data):
        return True

    @asynccontextmanager
    async def mock_lock(user_id):
        yield

    @asynccontextmanager
    async def mock_transaction():
        yield

    monkeypatch.setattr("systems.bot.commands.pit.ensure_user", mock_ensure_user)
    monkeypatch.setattr("systems.bot.commands.pit.save_user_data", mock_save_user_data)
    monkeypatch.setattr(database.db, "lock_user", mock_lock)
    monkeypatch.setattr(database.db, "transaction", mock_transaction)

    view = PitView("user1", fake_user["inventory"], pit_tier=1, pit_luck=10.0)
    view.selected_ids.add("exode")

    interaction = MagicMock()
    interaction.user.id = "user1"
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await view.on_confirm_sacrifice(interaction)

    expected_luck = round(10.0 + 0.09, 4)
    assert fake_user["pit_luck"] == expected_luck
    assert view.pit_luck == expected_luck
    assert "Pit Luck" in view.last_result_banner
    assert "+0.09" in view.last_result_banner


@pytest.mark.asyncio
async def test_pit_sacrifice_without_upgrade_awards_no_luck(monkeypatch):
    from systems.core import database

    exode_name = RARITY_DICT["exode"]
    fake_user = {
        "inventory": {exode_name: 10},
        "discovered": {exode_name: True},
        "upgrades": {"luck": {"pit_luck": 0}},
        "pit_luck": 0.0,
        "highscore": exode_name,
    }

    async def mock_ensure_user(user_id):
        return fake_user

    async def mock_save_user_data(user_id, data):
        return True

    @asynccontextmanager
    async def mock_lock(user_id):
        yield

    @asynccontextmanager
    async def mock_transaction():
        yield

    monkeypatch.setattr("systems.bot.commands.pit.ensure_user", mock_ensure_user)
    monkeypatch.setattr("systems.bot.commands.pit.save_user_data", mock_save_user_data)
    monkeypatch.setattr(database.db, "lock_user", mock_lock)
    monkeypatch.setattr(database.db, "transaction", mock_transaction)

    view = PitView("user1", fake_user["inventory"], pit_tier=0, pit_luck=0.0)
    view.selected_ids.add("exode")

    interaction = MagicMock()
    interaction.user.id = "user1"
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    await view.on_confirm_sacrifice(interaction)

    assert fake_user["pit_luck"] == 0.0
    assert view.pit_luck == 0.0
    assert "Pit Luck" not in view.last_result_banner
