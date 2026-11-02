# tests/bot/test_safeguard.py
"""
Tests for rate limiter tier consistency, kill switches, content safeguards,
and safety command modals.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import pytest

from systems.ai.providers import MODELS
from systems.bot.rate_limiter import DEFAULT_TIER_LIMITS
from systems.bot.commands.ask import AskCommand
from systems.bot.commands.analyze import AnalyzeCommand
from systems.bot.commands.txt2img import Txt2ImgCommand
from systems.bot.commands.tts import TTSCommand
from systems.bot.commands.transcribe import TranscribeCommand
from systems.bot.commands.safety import GuildPurgeModal
import systems.bot.commands.safety as safety_mod


def test_rate_limiter_tier_models_exist_in_models():
    """Every API ID in a tier list must correspond to some MODELS entry's id."""
    known_ids = {entry["id"] for entry in MODELS.values()}
    unknown = []
    for tier, data in DEFAULT_TIER_LIMITS.items():
        for model_id in data.get("models", []):
            if model_id not in known_ids:
                unknown.append(f"{tier}: {model_id}")

    assert not unknown, "Tier entries reference IDs not present in MODELS:\n  " + "\n  ".join(
        unknown
    )


@pytest.mark.asyncio
async def test_ask_command_blocked_by_kill_switch():
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

    with patch(
        "systems.bot.commands.ask.generate_response",
        new=AsyncMock(return_value="Unsafe content"),
    ):
        await cmd.prompt.callback(cmd, interaction, "Generate something unsafe")

    interaction.followup.send.assert_awaited_once()
    msg = interaction.followup.send.call_args[0][0]
    assert "🛡️ **Safeguard Block (unsafe_output)**" in msg
    assert "Explicit Content" in msg


@pytest.mark.asyncio
async def test_analyze_command_blocked_by_kill_switch():
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
    bot = MagicMock()
    bot.rate_limiter = MagicMock()
    bot.rate_limiter.check.return_value = (False, 0.0, "⛔ AI responses are temporarily disabled.")

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


@pytest.mark.asyncio
async def test_txt2img_safeguard_check():
    """Verify /txt2img rejects prompts flagged by check_safeguard."""
    mock_bot = MagicMock()
    mock_bot.rate_limiter = MagicMock()
    mock_bot.rate_limiter.check.return_value = (True, 0.0, None)
    mock_bot.check_safeguard = AsyncMock(
        return_value={"verdict": "unsafe_input", "reasoning": "NSFW", "violated_policy": "Explicit"}
    )
    txt2img_cog = Txt2ImgCommand(mock_bot)

    mock_interaction = MagicMock()
    mock_interaction.user.id = 12345
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    await txt2img_cog.txt2img.callback(txt2img_cog, mock_interaction, prompt="bad prompt")
    call_text = mock_interaction.followup.send.call_args[0][0]
    assert "Safeguard Block" in call_text


@pytest.mark.asyncio
async def test_guild_purge_modal_forum_and_unbound_local(monkeypatch):
    """Verifies that GuildPurgeModal handles ForumChannel and channels without history perms without crashing."""
    bot_mock = MagicMock()
    bot_mock.user.id = 99999

    text_chan = MagicMock(spec=discord.TextChannel)
    text_chan.permissions_for.return_value = MagicMock(read_message_history=False)
    text_chan.purge = AsyncMock()

    async def empty_archived(limit=None):
        if False:
            yield None

    text_chan.archived_threads = empty_archived

    forum_chan = MagicMock(spec=discord.ForumChannel)
    if hasattr(forum_chan, "purge"):
        del forum_chan.purge
    forum_chan.archived_threads = empty_archived

    guild_mock = MagicMock()
    guild_mock.name = "Test Guild"
    guild_mock.text_channels = [text_chan]
    guild_mock.forum_channels = [forum_chan]
    guild_mock.voice_channels = []
    guild_mock.stage_channels = []
    guild_mock.threads = []
    guild_mock.me = MagicMock()

    bot_mock.get_guild.return_value = guild_mock

    modal = GuildPurgeModal(bot_mock)
    modal.guild_id_input._value = "123456789012345678"
    modal.limit_input._value = "100"

    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_status_msg = MagicMock()
    mock_status_msg.edit = AsyncMock()
    mock_interaction.followup.send = AsyncMock(return_value=mock_status_msg)

    mock_db = MagicMock()
    mock_db._lock = asyncio.Lock()
    mock_db.conn.execute.return_value.__aenter__ = AsyncMock()
    mock_db.conn.execute.return_value.__aexit__ = AsyncMock()
    mock_db.conn.commit = AsyncMock()
    monkeypatch.setattr(safety_mod, "db", mock_db)

    await modal.on_submit(mock_interaction)
    mock_interaction.response.defer.assert_called_once()
    mock_status_msg.edit.assert_called()
