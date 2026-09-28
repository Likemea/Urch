# Urch/commands/transcribe.py
import os
import io
import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import config

GROQ_API_KEY = config.GROQ_API_KEY
GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
SUPPORTED_EXTENSIONS = (".mp3", ".mp4", ".m4a", ".wav", ".webm", ".flac", ".ogg")
MAX_FILE_SIZE = 25 * 1024 * 1024


async def transcribe_audio_from_bytes(audio_bytes: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    data = aiohttp.FormData()
    data.add_field("model", "whisper-large-v3-turbo")

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
    content_type = content_type_map.get(ext, "application/octet-stream")

    data.add_field("file", audio_bytes, filename=filename, content_type=content_type)

    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_AUDIO_URL, headers=headers, data=data) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("text", "")
            else:
                error_text = await response.text()
                raise Exception(f"HTTP {response.status}: {error_text}")


async def process_transcription(interaction: Interaction, attachment: discord.Attachment):
    filename = attachment.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        supported_str = ", ".join(SUPPORTED_EXTENSIONS)
        await interaction.followup.send(
            f"❌ Unsupported file extension `{ext}`. Supported formats are: {supported_str}"
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await interaction.followup.send("❌ File size exceeds the 25 MB limit for transcription.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(attachment.url) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to download audio attachment.")
                return
            audio_bytes = await resp.read()

    text = await transcribe_audio_from_bytes(audio_bytes, filename)
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

        await interaction.response.defer(thinking=True)
        try:
            await process_transcription(interaction, attachment)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot):
    await bot.add_cog(TranscribeCommand(bot))
