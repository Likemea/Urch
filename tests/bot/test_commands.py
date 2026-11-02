# tests/bot/test_commands.py
"""
Command registry verification, extension loading, duplicate checks,
and command execution tests (pixel, glitch, filter, transcribe, ocr, reactions).
"""

import io
import os
import pathlib
import random
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from PIL import Image
import pytest

from systems.game import utils
from systems.bot.commands.glitch import GlitchCommand, process_glitch
from systems.bot.commands.pixel import PixelCommand, _generate_pixel_image_sync
import systems.bot.commands.ocr as ocr_module
import systems.bot.commands.filter as filter_module
import systems.bot.commands.transcribe as transcribe_module

URCH_ROOT = pathlib.Path(__file__).resolve().parents[2]
COMMANDS_DIR = URCH_ROOT / "systems" / "bot" / "commands"


def _command_modules():
    if not COMMANDS_DIR.is_dir():
        return []
    return sorted(
        f"systems.bot.commands.{f[:-3]}"
        for f in os.listdir(COMMANDS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    )


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.reactions = True
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.mark.parametrize("mod", _command_modules())
def test_command_module_has_setup(mod):
    module = __import__(mod, fromlist=["setup"])
    assert hasattr(module, "setup"), f"{mod} has no setup(bot) function"
    assert callable(module.setup), f"{mod}.setup is not callable"


@pytest.mark.asyncio
@pytest.mark.parametrize("mod", _command_modules())
async def test_command_module_loads(bot, mod):
    try:
        await bot.load_extension(mod)
    except Exception as e:
        pytest.fail(f"Failed to load {mod}: {type(e).__name__}: {e}")


@pytest.mark.asyncio
async def test_all_commands_load_together(bot):
    errors = []
    for mod in _command_modules():
        try:
            await bot.load_extension(mod)
        except Exception as e:
            errors.append(f"{mod}: {type(e).__name__}: {e}")
    assert not errors, "Load failures:\n  " + "\n  ".join(errors)


@pytest.mark.asyncio
async def test_no_duplicate_slash_command_names(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    names = [cmd.name for cmd in bot.tree.get_commands()]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate slash-command names: {duplicates}"


@pytest.mark.asyncio
async def test_no_duplicate_prefix_command_names(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    names = [cmd.name for cmd in bot.commands]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate prefix-command names: {duplicates}"


@pytest.mark.asyncio
async def test_slash_commands_have_descriptions(bot):
    for mod in _command_modules():
        await bot.load_extension(mod)

    missing = [
        cmd.qualified_name
        for cmd in bot.tree.get_commands(type=discord.AppCommandType.chat_input)
        if not getattr(cmd, "description", None)
    ]
    assert not missing, f"Slash commands missing descriptions: {missing}"


@pytest.mark.asyncio
async def test_pixel_isolates_rng_and_uses_to_thread():
    random.seed(42)
    expected_first = random.random()

    random.seed(42)
    _generate_pixel_image_sync(seed=999999, size=16, palette="random", pattern="random")
    actual_first = random.random()
    assert actual_first == expected_first, "Global RNG state was poisoned by pixel generation!"

    bot_mock = MagicMock()
    cmd = PixelCommand(bot_mock)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch(
        "systems.bot.commands.pixel.asyncio.to_thread",
        wraps=utils.db and __import__("asyncio").to_thread,
    ) as spy_thread:
        await cmd.pixel.callback(
            cmd, interaction, seed=12345, size=16, palette="random", pattern="noise"
        )
        spy_thread.assert_called_once()
        interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_glitch_preserves_gif_frames():
    frames = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        img = Image.new("RGB", (64, 64), color=color)
        frames.append(img)

    gif_buf = io.BytesIO()
    frames[0].save(
        gif_buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    gif_bytes = gif_buf.getvalue()

    output_bytes = process_glitch(gif_bytes, is_gif=True, intensity=5)
    assert len(output_bytes) > 0

    out_img = Image.open(io.BytesIO(output_bytes))
    num_frames = 0
    try:
        while True:
            num_frames += 1
            out_img.seek(out_img.tell() + 1)
    except EOFError:
        pass

    assert num_frames == 3, f"Expected 3 frames in output GIF, got {num_frames}"


@pytest.mark.asyncio
async def test_glitch_attachment_none_content_type():
    bot_mock = MagicMock()
    cmd = GlitchCommand(bot_mock)

    img = Image.new("RGB", (32, 32), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    data = buf.getvalue()

    mock_attachment = MagicMock()
    mock_attachment.content_type = None
    mock_attachment.filename = "test_image.png"
    mock_attachment.size = len(data)
    mock_attachment.read = AsyncMock(return_value=data)

    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    await cmd.glitch.callback(cmd, mock_interaction, image=mock_attachment, intensity=3)
    mock_interaction.followup.send.assert_called_once()


@pytest.mark.asyncio
async def test_ocr_size_limit_and_rate_limit():
    mock_bot = MagicMock()
    mock_bot.rate_limiter = MagicMock()
    mock_bot.rate_limiter.check.return_value = (True, 0.0, None)
    ocr_cog = ocr_module.OCRCommand(mock_bot)

    mock_interaction = MagicMock()
    mock_interaction.user.id = 12345
    mock_interaction.response.send_message = AsyncMock()

    mock_file = MagicMock()
    mock_file.size = 10 * 1024 * 1024
    mock_file.content_type = "image/png"

    await ocr_cog.ocr_slash.callback(ocr_cog, mock_interaction, mock_file)
    mock_interaction.response.send_message.assert_called_with(
        "❌ Image is too large (maximum allowed size is 8 MB).", ephemeral=True
    )


@pytest.mark.asyncio
async def test_filter_rejects_oversized_avatar():
    bot_mock = MagicMock()
    cog = filter_module.FilterCommand(bot_mock)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.display_avatar.url = "https://cdn.discordapp.com/avatars/1/2.png"
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.content_length = filter_module.MAX_AVATAR_BYTES + 1024

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(filter_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("systems.ai.providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        choice = MagicMock()
        choice.value = "blur"
        await cog.filter.callback(cog, interaction, style=choice, user=None)
        interaction.followup.send.assert_awaited_once()
        assert "too large" in interaction.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_transcribe_streams_bounded_and_cleans_up_tempfile():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.followup.send = AsyncMock()

    attachment = MagicMock(spec=discord.Attachment)
    attachment.filename = "voice.mp3"
    attachment.size = 1000
    attachment.url = "https://cdn.discordapp.com/attachments/1/2/voice.mp3"

    async def oversized_chunks(_chunk_size):
        yield b"x" * (transcribe_module.MAX_FILE_SIZE + 10)

    mock_resp_over = MagicMock()
    mock_resp_over.status = 200
    mock_resp_over.content_length = None
    mock_resp_over.content.iter_chunked = oversized_chunks

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp_over)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(transcribe_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("systems.ai.providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        await transcribe_module.process_transcription(interaction, attachment)
        interaction.followup.send.assert_awaited_once_with(
            "❌ File size exceeds the 25 MB limit for transcription."
        )

    interaction.followup.send.reset_mock()
    recorded_temp_paths = []

    async def valid_chunks(_chunk_size):
        yield b"fake mp3 audio content"

    mock_resp_ok = MagicMock()
    mock_resp_ok.status = 200
    mock_resp_ok.content_length = 22
    mock_resp_ok.content.iter_chunked = valid_chunks

    mock_post_resp = MagicMock()
    mock_post_resp.status = 200
    mock_post_resp.json = AsyncMock(return_value={"text": "Hello from audio"})

    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp_ok)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_post_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    orig_transcribe = transcribe_module.transcribe_audio_from_bytes

    async def spy_transcribe(source, fname):
        assert isinstance(source, str) and os.path.exists(source)
        recorded_temp_paths.append(source)
        return await orig_transcribe(source, fname)

    with (
        patch.object(transcribe_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("systems.ai.providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        with patch.object(
            transcribe_module, "transcribe_audio_from_bytes", side_effect=spy_transcribe
        ):
            await transcribe_module.process_transcription(interaction, attachment)

    assert len(recorded_temp_paths) == 1
    assert not os.path.exists(recorded_temp_paths[0]), "Temp audio file was not cleaned up!"
    interaction.followup.send.assert_awaited_once()
    assert "Hello from audio" in interaction.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_on_raw_reaction_add_uses_original_author_id(fresh_db, monkeypatch):
    """Verify that when an admin reacts with ♻️, the original author's ID is passed to generate_response."""
    import main as main_mod

    guild_id = "888888"
    channel_id = "777777"
    orig_author_id = 111111
    admin_reactor_id = 999999
    bot_user_id = 555555

    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="user",
        content="Original user question",
        message_ids=[2001],
        author_id=str(orig_author_id),
        channel_id=channel_id,
    )
    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="assistant",
        content="Initial bot answer",
        message_ids=[2002],
        author_id=str(orig_author_id),
        channel_id=channel_id,
    )

    mock_bot_user = MagicMock()
    mock_bot_user.id = bot_user_id
    monkeypatch.setattr(main_mod.bot, "_connection", MagicMock(user=mock_bot_user))

    mock_orig_user = MagicMock()
    mock_orig_user.id = orig_author_id
    mock_orig_user.name = "OriginalUser"

    mock_channel = MagicMock()
    mock_channel.id = int(channel_id)
    mock_message = MagicMock()
    mock_message.id = 2002
    mock_message.author.id = bot_user_id
    mock_message.channel = mock_channel
    mock_message.guild = MagicMock(id=int(guild_id))
    mock_message.remove_reaction = AsyncMock()
    mock_message.edit = AsyncMock()
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)

    monkeypatch.setattr(main_mod.bot, "get_channel", MagicMock(return_value=mock_channel))
    monkeypatch.setattr(
        main_mod.bot,
        "get_user",
        MagicMock(side_effect=lambda uid: mock_orig_user if uid == orig_author_id else None),
    )

    mock_generate = AsyncMock(
        return_value={
            "raw_response": "Regenerated answer",
            "display_response": "Regenerated answer",
        }
    )
    monkeypatch.setattr(main_mod, "generate_response", mock_generate)
    monkeypatch.setattr(main_mod, "check_safeguard", AsyncMock(return_value={"verdict": "safe"}))

    payload = MagicMock()
    payload.user_id = admin_reactor_id
    payload.channel_id = int(channel_id)
    payload.guild_id = int(guild_id)
    payload.message_id = 2002
    payload.emoji = "♻️"
    payload.member = MagicMock()
    payload.member.guild_permissions.administrator = True

    await main_mod.on_raw_reaction_add(payload)

    mock_generate.assert_awaited_once()
    call_args = mock_generate.call_args
    assert call_args.args[2] == str(orig_author_id)
    assert call_args.kwargs["user"].id == orig_author_id
