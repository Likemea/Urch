# Urch/tests/test_audit_items_1_2_15.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from raritylist import RARITIES
from commands.leaderboard import LeaderboardView
from commands.settings import (
    ModelSelect,
    ReasoningSelect,
    ToolingSelect,
    AVAILABLE_TOOLS,
    get_model_page_data,
)
from functions.tools_schema import AGENT_TOOLS
from providers import MODELS


# ─────────────────────────────────────────────────────────────
# 1. Leaderboard Tests (Item 1)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_leaderboard_discovered_max_rarities_no_index_error():
    """Verify that a player who has discovered ALL rarities does not crash format_page."""
    bot = MagicMock()
    bot.get_user.return_value = None

    view = LeaderboardView(bot)
    view.category = "discovered"

    # Mock user who discovered all rarities
    all_discovered_count = len(RARITIES)
    mock_data = [("123456789", all_discovered_count), ("987654321", 5)]

    embed = await view.format_page(data=mock_data)
    assert embed is not None
    assert f"[{all_discovered_count}/{len(RARITIES)}]" in embed.description
    assert f"**{all_discovered_count}**" not in embed.description  # formatted correctly


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

    # get_leaderboard_data must be called exactly once
    assert view.get_leaderboard_data.call_count == 1
    interaction.response.edit_message.assert_awaited_once()


# ─────────────────────────────────────────────────────────────
# 2. Rate Limiter, Kill Switch, and Safeguard Tests (Item 2)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_command_blocked_by_kill_switch():
    from commands.ask import AskCommand

    bot = MagicMock()
    bot.rate_limiter = MagicMock()
    bot.rate_limiter.check.return_value = (False, 0.0, "⛔ AI responses are temporarily disabled.")

    cmd = AskCommand(bot)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    await cmd.prompt.callback(cmd, interaction, "Hello")

    interaction.response.send_message.assert_awaited_once_with(
        "⛔ AI responses are temporarily disabled.", ephemeral=True
    )
    interaction.response.defer.assert_not_called()


@pytest.mark.asyncio
async def test_ask_command_safeguard_block():
    from commands.ask import AskCommand

    bot = MagicMock()
    bot.rate_limiter = MagicMock()
    bot.rate_limiter.check.return_value = (True, 0.0, "")
    bot.check_safeguard = AsyncMock(
        return_value={
            "verdict": "unsafe_output",
            "reasoning": "Detected policy violation.",
            "violated_policy": "Explicit Content",
        }
    )

    cmd = AskCommand(bot)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch("commands.ask.generate_response", new=AsyncMock(return_value="Unsafe content")):
        await cmd.prompt.callback(cmd, interaction, "Generate something unsafe")

    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "🛡️ **Safeguard Block (unsafe_output)**" in msg
    assert "Explicit Content" in msg


@pytest.mark.asyncio
async def test_analyze_command_blocked_by_kill_switch():
    from commands.analyze import AnalyzeCommand

    bot = MagicMock()
    bot.rate_limiter = MagicMock()
    bot.rate_limiter.check.return_value = (False, 0.0, "⛔ AI responses are temporarily disabled.")

    cmd = AnalyzeCommand(bot)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    file_att = MagicMock(spec=discord.Attachment)
    file_att.content_type = "image/png"

    await cmd.analyze_slash.callback(cmd, interaction, file_att, "Analyze this")

    interaction.response.send_message.assert_awaited_once_with(
        "⛔ AI responses are temporarily disabled.", ephemeral=True
    )
    interaction.response.defer.assert_not_called()


@pytest.mark.asyncio
async def test_txt2img_tts_transcribe_blocked_by_kill_switch():
    from commands.txt2img import Txt2ImgCommand
    from commands.tts import TTSCommand
    from commands.transcribe import TranscribeCommand

    bot = MagicMock()
    bot.rate_limiter = MagicMock()
    bot.rate_limiter.check.return_value = (False, 0.0, "⛔ AI responses are temporarily disabled.")

    # txt2img
    cmd1 = Txt2ImgCommand(bot)
    int1 = MagicMock(spec=discord.Interaction)
    int1.user.id = 123
    int1.response.send_message = AsyncMock()
    int1.response.defer = AsyncMock()
    await cmd1.txt2img.callback(cmd1, int1, "a sunset")
    int1.response.send_message.assert_awaited_once_with(
        "⛔ AI responses are temporarily disabled.", ephemeral=True
    )
    int1.response.defer.assert_not_called()

    # tts
    cmd2 = TTSCommand(bot)
    int2 = MagicMock(spec=discord.Interaction)
    int2.user.id = 123
    int2.response.send_message = AsyncMock()
    int2.response.defer = AsyncMock()
    await cmd2.tts.callback(cmd2, int2, "hello world")
    int2.response.send_message.assert_awaited_once_with(
        "⛔ AI responses are temporarily disabled.", ephemeral=True
    )
    int2.response.defer.assert_not_called()

    # transcribe
    cmd3 = TranscribeCommand(bot)
    int3 = MagicMock(spec=discord.Interaction)
    int3.user.id = 123
    int3.response.send_message = AsyncMock()
    int3.response.defer = AsyncMock()
    audio_att = MagicMock(spec=discord.Attachment)
    await cmd3.transcribe_slash.callback(cmd3, int3, file=audio_att)
    int3.response.send_message.assert_awaited_once_with(
        "⛔ AI responses are temporarily disabled.", ephemeral=True
    )
    int3.response.defer.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 3. Settings & Agent Tests (Item 15)
# ─────────────────────────────────────────────────────────────


def test_model_select_options_never_exceed_discord_limit():
    """Verify that ModelSelect limits options per page to <= 25 even if 35 models are configured."""
    fake_models = {f"model_{i}": {"disp": f"Model {i}", "id": f"m/{i}"} for i in range(35)}

    with patch("commands.settings.MODEL_LIST", fake_models):
        chunks = get_model_page_data()
        assert len(chunks) > 1
        for page_idx in range(len(chunks)):
            select = ModelSelect(user_id="123", current_model="Auto", page=page_idx)
            assert len(select.options) <= 25


def test_tooling_select_options_and_defaults():
    """Verify multi-select ToolingSelect checkboxes properly parse enabled tools."""
    # All enabled
    select1 = ToolingSelect("123", "Auto")
    assert select1.min_values == 0
    assert select1.max_values == len(AVAILABLE_TOOLS)
    assert all(opt.default for opt in select1.options)

    # Selective enabled
    select2 = ToolingSelect("123", "web_search,generate_media")
    defaults = {opt.value: opt.default for opt in select2.options}
    assert defaults["web_search"] is True
    assert defaults["generate_media"] is True
    assert defaults["fetch_webpage"] is False
    assert defaults["execute_code"] is False

    # Disabled
    select3 = ToolingSelect("123", "False")
    assert not any(opt.default for opt in select3.options)


@pytest.mark.asyncio
async def test_agent_tool_filtering():
    """Verify agent.py runs with only user-enabled tools."""
    from agent import run_agent_loop

    user_params = {"tooling": "web_search,execute_code", "reasoning": "none"}
    base_messages = [{"role": "user", "content": "test prompt"}]

    captured_payload = None

    async def mock_call_provider(key, payload):
        nonlocal captured_payload
        captured_payload = payload
        return {"choices": [{"message": {"content": "Final answer"}}]}, "qwen/qwen3.8-27b"

    with patch("agent.call_provider", new=mock_call_provider):
        await run_agent_loop("qwen3.8-27b", base_messages, user_params)

    assert captured_payload is not None
    # Check that tools only contain web_search and execute_code
    tool_names = [t["function"]["name"] for t in captured_payload.get("tools", [])]
    assert set(tool_names) == {"web_search", "execute_code"}

    # Check that reasoning_effort: "none" is explicitly present
    assert captured_payload.get("reasoning_effort") == "none"


@pytest.mark.asyncio
async def test_agent_tooling_disabled():
    """Verify agent.py omits tools when user sets tooling to False."""
    from agent import run_agent_loop

    user_params = {"tooling": "False", "reasoning": "low"}
    base_messages = [{"role": "user", "content": "test prompt"}]

    captured_payload = None

    async def mock_call_provider(key, payload):
        nonlocal captured_payload
        captured_payload = payload
        return {"choices": [{"message": {"content": "Final answer"}}]}, "qwen/qwen3.8-27b"

    with patch("agent.call_provider", new=mock_call_provider):
        await run_agent_loop("qwen3.8-27b", base_messages, user_params)

    assert captured_payload is not None
    assert "tools" not in captured_payload
    assert "tool_choice" not in captured_payload
    assert captured_payload.get("reasoning_effort") == "low"
