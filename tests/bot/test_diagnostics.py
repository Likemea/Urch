# tests/bot/test_diagnostics.py
"""
Tests for /diagnose concurrency and event loop safety, and /settings UI components.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import pytest

from systems.bot.commands.safety import OWNER_ID
from systems.bot.commands.settings import (
    AVAILABLE_TOOLS,
    ModelSelect,
    ToolingSelect,
    get_model_page_data,
)
import systems.bot.commands.diagnose as diagnose_module


@pytest.mark.asyncio
async def test_diagnose_restricted_to_owner():
    bot = MagicMock()
    cog = diagnose_module.DiagnoseCommand(bot)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 999999999  # Not OWNER_ID
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    await cog.diagnose.callback(cog, interaction, duration=5)
    interaction.response.send_message.assert_awaited_once_with(
        "⛔ This command is restricted.", ephemeral=True
    )
    interaction.response.defer.assert_not_called()


@pytest.mark.asyncio
async def test_diagnose_prevents_concurrent_runs_and_uses_to_thread():
    bot = MagicMock()
    bot.latency = 0.05
    bot.rate_limiter = None
    cog = diagnose_module.DiagnoseCommand(bot)

    async with cog._lock:
        int_concurrent = MagicMock(spec=discord.Interaction)
        int_concurrent.user.id = OWNER_ID
        int_concurrent.response.send_message = AsyncMock()
        await cog.diagnose.callback(cog, int_concurrent, duration=1)
        int_concurrent.response.send_message.assert_awaited_once()
        assert "already in progress" in int_concurrent.response.send_message.call_args.args[0]

    int_owner = MagicMock(spec=discord.Interaction)
    int_owner.user.id = OWNER_ID
    int_owner.response.defer = AsyncMock()
    int_owner.followup.send = AsyncMock()

    with patch.object(
        diagnose_module.asyncio,
        "to_thread",
        wraps=asyncio.to_thread,
    ) as spy_to_thread:
        await cog.diagnose.callback(cog, int_owner, duration=1)
        spy_to_thread.assert_called_once()
        assert spy_to_thread.call_args.args[0] is diagnose_module._render_diagnostics_sync
        int_owner.followup.send.assert_awaited_once()


def test_model_select_options_never_exceed_discord_limit():
    """Verify that ModelSelect limits options per page to <= 25 even if 35 models are configured."""
    fake_models = {f"model_{i}": {"disp": f"Model {i}", "id": f"m/{i}"} for i in range(35)}

    with patch("systems.bot.commands.settings.MODEL_LIST", fake_models):
        chunks = get_model_page_data()
        assert len(chunks) > 1
        for page_idx in range(len(chunks)):
            select = ModelSelect(user_id="123", current_model="Auto", page=page_idx)
            assert len(select.options) <= 25


def test_tooling_select_options_and_defaults():
    """Verify multi-select ToolingSelect checkboxes properly parse enabled tools."""
    select1 = ToolingSelect("123", "Auto")
    assert select1.min_values == 0
    assert select1.max_values == len(AVAILABLE_TOOLS)
    assert all(opt.default for opt in select1.options)

    select2 = ToolingSelect("123", "web_search,generate_media")
    defaults = {opt.value: opt.default for opt in select2.options}
    assert defaults["web_search"] is True
    assert defaults["generate_media"] is True
    assert defaults["fetch_webpage"] is False
    assert defaults["execute_code"] is False

    select3 = ToolingSelect("123", "False")
    assert not any(opt.default for opt in select3.options)
