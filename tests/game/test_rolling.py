# tests/game/test_rolling.py
"""
Tests for rolling mechanics, autorolls, currency/inventory routing, and leaderboard views.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
import discord

from systems.bot.commands.leaderboard import LeaderboardView
from systems.game.raritylist import RARITIES
from systems.game.utils import (
    currency_add,
    currency_count,
    currency_remove,
    process_autorolls,
    roll_rarities,
)


@pytest.mark.asyncio
async def test_currency_add_remove_roundtrip(fresh_db):
    await fresh_db.ensure_user("u5")

    await currency_add("u5", "clovers", 10)
    assert await currency_count("u5", "clovers") == 10

    assert await currency_remove("u5", "clovers", 4) is True
    assert await currency_count("u5", "clovers") == 6

    assert await currency_remove("u5", "clovers", 999) is False
    assert await currency_count("u5", "clovers") == 6


@pytest.mark.asyncio
async def test_inventory_vs_currency_routing(fresh_db):
    """`resolve_item_key` must route names/ids to inventory and the rest to currency."""
    await fresh_db.ensure_user("u6")
    rarity_name = RARITIES[0][0]

    await currency_add("u6", rarity_name, 3)
    await currency_add("u6", "clovers", 5)

    data = await fresh_db.get_user_data("u6")
    assert data["inventory"].get(rarity_name) == 3
    assert data["currencies"].get("clovers") == 5


@pytest.mark.asyncio
async def test_roll_rarities_returns_valid_names(fresh_db):
    rarity_names = {r[0] if isinstance(r, (tuple, list)) else r for r in RARITIES}

    await fresh_db.ensure_user("u10")
    results = await roll_rarities("u10", count=25, provided_luck=1.0)
    assert len(results) == 25
    assert all(r in rarity_names for r in results)


@pytest.mark.asyncio
async def test_roll_rarities_high_luck_biases_rarity(fresh_db):
    """High luck should not produce *worse* average rank than low luck."""
    await fresh_db.ensure_user("u11")
    order = {r[0]: i for i, r in enumerate(RARITIES)}

    low = await roll_rarities("u11", count=500, provided_luck=1.0)
    high = await roll_rarities("u11", count=500, provided_luck=1000.0)

    avg_low = sum(order[r] for r in low) / len(low)
    avg_high = sum(order[r] for r in high) / len(high)
    assert avg_high >= avg_low, f"Luck inversion: low={avg_low:.2f} high={avg_high:.2f}"


@pytest.mark.asyncio
async def test_process_autorolls_does_not_crash(fresh_db):
    await fresh_db.ensure_user("u12")
    await fresh_db.set_autoroll_status("u12", True)

    rare_hits = await process_autorolls(["u12"])
    assert isinstance(rare_hits, list)

    data = await fresh_db.get_user_data("u12")
    assert data["roll_count"] >= 1, "Autoroll did not increment roll_count"


@pytest.mark.asyncio
async def test_leaderboard_discovered_max_rarities_no_index_error():
    """Verify that a player who has discovered ALL rarities does not crash format_page."""
    bot = MagicMock()
    bot.get_user.return_value = None

    view = LeaderboardView(bot)
    view.category = "discovered"

    all_discovered_count = len(RARITIES)
    mock_data = [("123456789", all_discovered_count), ("987654321", 5)]

    embed = await view.format_page(data=mock_data)
    assert embed is not None
    assert f"[{all_discovered_count}/{len(RARITIES)}]" in embed.description
    assert f"**{all_discovered_count}**" not in embed.description


@pytest.mark.asyncio
async def test_leaderboard_queries_only_once_per_click():
    """Verify that button callbacks only query get_leaderboard_data once."""
    bot = MagicMock()
    view = LeaderboardView(bot)

    mock_data = [("123", 10), ("456", 20)]
    view.get_leaderboard_data = AsyncMock(return_value=mock_data)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.response.edit_message = AsyncMock()

    await view.show_luck.callback(interaction)

    assert view.get_leaderboard_data.call_count == 1
    interaction.response.edit_message.assert_awaited_once()
