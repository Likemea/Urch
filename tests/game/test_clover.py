# tests/game/test_clover.py
"""
Tests for clover drop probability, independent roll trials, clover gain upgrades,
and incremental clover calculation.
"""

from unittest.mock import AsyncMock, patch
import pytest

from systems.game import utils
from systems.game.upgrades import get_upgrade_effect
from systems.game.upgrades.clover_upgrades import CLOVER_UPGRADES


def test_clover_gain_upgrade_chance_scaling():
    """Verify Clover Gain scales from 10% base to 50% at Tier 8 (+5% per tier)."""
    upg = CLOVER_UPGRADES["clover_gain"]
    assert upg["max_tier"] == 8

    effects_t0 = get_upgrade_effect("user1", {"upgrades": {"clover": {}}})
    assert effects_t0["clover_chance"] == pytest.approx(0.10)

    for tier in range(1, 9):
        effects = get_upgrade_effect("user1", {"upgrades": {"clover": {"clover_gain": tier}}})
        expected_chance = 0.10 + 0.05 * tier
        assert effects["clover_chance"] == pytest.approx(expected_chance)

    effects_t8 = get_upgrade_effect("user1", {"upgrades": {"clover": {"clover_gain": 8}}})
    assert effects_t8["clover_chance"] == pytest.approx(0.50)


@pytest.mark.asyncio
async def test_clover_drop_below_luck_threshold(fresh_db, monkeypatch):
    """Under 10,000 luck, no clovers should drop even if random returns 0.0."""
    monkeypatch.setattr(utils, "db", fresh_db)
    user_id = "low_luck_user"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["luck_multi"] = 500.0  # < 10,000
    await fresh_db.save_user_data(user_id, user)

    with patch("random.random", return_value=0.0):
        updated = await utils.update_user_data(user_id, ["Common"] * 5, action="keep")

    assert updated.get("last_earned_clovers", 0) == 0
    assert updated.get("currencies", {}).get("clovers", 0) == 0
    assert updated.get("clovers_earned", 0) == 0


@pytest.mark.asyncio
async def test_clover_drop_at_luck_threshold_independent_trials(fresh_db, monkeypatch):
    """At >= 10,000 luck, each roll is an independent trial against clover_chance."""
    monkeypatch.setattr(utils, "db", fresh_db)
    user_id = "high_luck_user"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["luck_multi"] = 10000.0
    await fresh_db.save_user_data(user_id, user)

    roll_randoms = [0.02, 0.50, 0.08, 0.90]
    with patch("random.random", side_effect=roll_randoms):
        updated = await utils.update_user_data(user_id, ["Common"] * 4, action="keep")

    assert updated["last_earned_clovers"] == 2
    assert updated["currencies"]["clovers"] == 2
    assert updated["clovers_earned"] == 2


@pytest.mark.asyncio
async def test_clover_drop_with_clover_gain_upgrade_and_multipliers(fresh_db, monkeypatch):
    """Tier 8 gives 50% chance, and clover_mult doubles earned clovers."""
    monkeypatch.setattr(utils, "db", fresh_db)
    user_id = "max_gain_user"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["luck_multi"] = 12000.0
    user["upgrades"] = {"clover": {"clover_gain": 8}}  # 50% chance
    await fresh_db.save_user_data(user_id, user)

    roll_randoms = [0.15, 0.45, 0.55, 0.01]
    with patch("random.random", side_effect=roll_randoms):
        updated = await utils.update_user_data(
            user_id, ["Common"] * 4, action="keep", clover_mult=2.0
        )

    assert updated["last_earned_clovers"] == 6
    assert updated["currencies"]["clovers"] == 6
    assert updated["clovers_earned"] == 6


@pytest.mark.asyncio
async def test_clover_base_multiplier_calculation(fresh_db):
    """Verify clover multiplier does not double-count base 1.0."""
    await fresh_db.ensure_user(1234)
    with (
        patch(
            "systems.game.buffs.evaluate_active_buffs",
            AsyncMock(return_value={"clover_mult": 1.0}),
        ),
        patch("random.random", return_value=0.05),
    ):
        user = await fresh_db.get_user_data(1234)
        user["luck_multi"] = 10000.0
        user["roll_count"] = 99
        await fresh_db.save_user_data(1234, user)

        updated = await utils.update_user_data(1234, "Common", action="keep")
        assert updated["currencies"]["clovers"] == 1


@pytest.mark.asyncio
async def test_clover_incremental_calculation_no_retroactive_nor_lockout(fresh_db, monkeypatch):
    """
    Verifies that clovers are awarded incrementally per roll batch.
    - Large roll history does not retroactively award clovers when clover_mult increases.
    - Post-potion expiration does not lock out future clover awards.
    """
    monkeypatch.setattr(utils, "db", fresh_db)

    user_id = "clover_tester"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["luck_multi"] = 15000.0  # effective_luck >= 10000
    user["roll_count"] = 50000
    user["clovers_earned"] = 5000
    user["currencies"] = {"clovers": 5000}
    await fresh_db.save_user_data(user_id, user)

    with patch("random.random", side_effect=[0.05] + [0.99] * 9):
        updated = await utils.update_user_data(
            user_id, ["Common"] * 10, action="keep", clover_mult=2.0
        )
    assert updated["roll_count"] == 50010
    assert updated["clovers_earned"] == 5002
    assert updated["currencies"]["clovers"] == 5002

    with patch("random.random", side_effect=[0.05] + [0.99] * 9):
        updated_after_expiry = await utils.update_user_data(
            user_id, ["Common"] * 10, action="keep", clover_mult=1.0
        )
    assert updated_after_expiry["roll_count"] == 50020
    assert updated_after_expiry["clovers_earned"] == 5003
    assert updated_after_expiry["currencies"]["clovers"] == 5003
