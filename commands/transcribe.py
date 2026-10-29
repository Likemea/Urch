# Urch/commands/transcribe.py
import os
import io
import tempfile
from typing import Union
import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import config
from providers import get_session

GROQ_API_KEY = config.GROQ_API_KEY
GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
SUPPORTED_EXTENSIONS = (".mp3", ".mp4", ".m4a", ".wav", ".webm", ".flac", ".ogg")
MAX_FILE_SIZE = 25 * 1024 * 1024
STREAM_CHUNK_SIZE = 64 * 1024


def _get_audio_content_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    content_type_map = {
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".m4a": "audio/m4a",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
    }
    return content_type_map.get(ext, "application/octet-stream")


async def _download_bounded_to_tempfile(
    resp: aiohttp.ClientResponse, max_bytes: int, suffix: str
) -> str:
    """Streams an HTTP response to a temporary file on disk, enforcing a strict byte ceiling."""
    if getattr(resp, "content_length", None) and resp.content_length > max_bytes:
        raise ValueError("File size exceeds the 25 MB limit for transcription.")

    fd, tmp_path = tempfile.mkstemp(prefix="urch_audio_", suffix=suffix)
    total_bytes = 0
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            content = getattr(resp, "content", None)
            if content is not None and hasattr(content, "iter_chunked"):
                async for chunk in content.iter_chunked(STREAM_CHUNK_SIZE):
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError("File size exceeds the 25 MB limit for transcription.")
                    tmp_file.write(chunk)
            elif content is not None and hasattr(content, "read"):
                data = await content.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError("File size exceeds the 25 MB limit for transcription.")
                tmp_file.write(data)
            else:
                data = await resp.read()
                if len(data) > max_bytes:
                    raise ValueError("File size exceeds the 25 MB limit for transcription.")
                tmp_file.write(data)
        return tmp_path
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


async def transcribe_audio_from_bytes(
    audio_source: Union[bytes, bytearray, io.IOBase, str, os.PathLike], filename: str
) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    content_type = _get_audio_content_type(filename)

    opened_file = None
    try:
        if isinstance(audio_source, (str, os.PathLike)):
            file_size = os.path.getsize(audio_source)
            if file_size > MAX_FILE_SIZE:
                raise ValueError("File size exceeds the 25 MB limit for transcription.")
            opened_file = open(audio_source, "rb")
            file_payload = opened_file
        elif isinstance(audio_source, (bytes, bytearray)):
            if len(audio_source) > MAX_FILE_SIZE:
                raise ValueError("File size exceeds the 25 MB limit for transcription.")
            file_payload = io.BytesIO(audio_source)
        else:
            file_payload = audio_source

        data = aiohttp.FormData()
        data.add_field("model", "whisper-large-v3-turbo")
        data.add_field("file", file_payload, filename=filename, content_type=content_type)

        session = await get_session()
        async with session.post(
            GROQ_AUDIO_URL, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("text", "")
            else:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text[:500]}")
    finally:
        if opened_file is not None:
            opened_file.close()


async def process_transcription(interaction: Interaction, attachment: discord.Attachment):
    filename = attachment.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        supported_str = ", ".join(SUPPORTED_EXTENSIONS)
        await interaction.followup.send(
            f"❌ Unsupported file extension `{ext}`. Supported formats are: {supported_str}"
        )
        return

    if attachment.size and attachment.size > MAX_FILE_SIZE:
        await interaction.followup.send("❌ File size exceeds the 25 MB limit for transcription.")
        return

    tmp_path = None
    try:
        session = await get_session()
        async with session.get(attachment.url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to download audio attachment.")
                return
            try:
                tmp_path = await _download_bounded_to_tempfile(resp, MAX_FILE_SIZE, ext)
            except ValueError:
                await interaction.followup.send(
                    "❌ File size exceeds the 25 MB limit for transcription."
                )
                return

        text = await transcribe_audio_from_bytes(tmp_path, filename)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    text = text.strip()

    if not text:
        await interaction.followup.send("⚠️ No speech or text detected in the audio file.")
        return

    if len(text) > 1900:
        with io.BytesIO(text.encode("utf-8")) as f:
            f.name = "transcription.txt"
            await interaction.followup.send(
                "📄 Transcription was too long, sent as file:", file=discord.File(f)
            )
    else:
        await interaction.followup.send(f"🎙️ **Transcription**\n```{text}```")


class TranscribeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.ctx_menu = app_commands.ContextMenu(
            name="Transcribe", callback=self.transcribe_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="transcribe", description="Transcribe an audio file attachment")
    @app_commands.describe(file="Upload an audio file to transcribe (.mp3, .wav, .m4a, .ogg, etc.)")
    async def transcribe_slash(self, interaction: discord.Interaction, file: discord.Attachment):
        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(str(interaction.user.id), tier="medium")
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                await interaction.response.send_message(msg, ephemeral=True)
                return

        await interaction.response.defer(thinking=True)
        try:
            await process_transcription(interaction, file)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")

    async def transcribe_context(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message(
                "❌ No attachment found on this message.", ephemeral=True
            )
            return

        attachment = message.attachments[0]
        ext = os.path.splitext(attachment.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            await interaction.response.send_message(
                f"❌ Attachment is not a supported audio file ({ext}).", ephemeral=True
            )
            return

        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(str(interaction.user.id), tier="medium")
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                await interaction.response.send_message(msg, ephemeral=True)
                return

        await interaction.response.defer(thinking=True)
        try:
            await process_transcription(interaction, attachment)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot):
    await bot.add_cog(TranscribeCommand(bot))
