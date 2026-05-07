# Urch/commands/ocr.py
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import pytesseract
from PIL import Image
import io
import aiohttp
import asyncio

async def process_ocr_from_url(url: str, interaction: Interaction, loop: asyncio.AbstractEventLoop):    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to download image")
                return
            image_data = await resp.read()

    def run_tesseract(data):
        image = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(image)

    text = await loop.run_in_executor(None, run_tesseract, image_data)

    if not text.strip():
        await interaction.followup.send("⚠️ No text detected")
        return

    if len(text) > 1900:
        with io.BytesIO(text.encode('utf-8')) as f:
            f.name = "ocr_result.txt"
            await interaction.followup.send("📄 Text was too long, sent as file:", file=discord.File(f))
    else:
        await interaction.followup.send(f"**📄 Result**\n```\n{text}\n```")


class OCRCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.ctx_menu = app_commands.ContextMenu(
            name="OCR",
            callback=self.ocr_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    # -----------------------------------------------------
    # A. SLASH COMMAND (/ocr)
    # -----------------------------------------------------
    @app_commands.command(name="ocr", description="Extract text from an image attachment")
    @app_commands.describe(file="Upload an image to extract text from")
    async def ocr_slash(self, interaction: discord.Interaction, file: discord.Attachment):
        if not file.content_type or not file.content_type.startswith('image'):
            await interaction.response.send_message("❌ Please upload a valid image file.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            loop = asyncio.get_running_loop()
            await process_ocr_from_url(file.url, interaction, loop)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")

    # -----------------------------------------------------
    # B. CONTEXT MENU CALLBACK
    # -----------------------------------------------------
    async def ocr_context(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message("❌ No image attachment found", ephemeral=True)
            return
            
        attachment = message.attachments[0]
        if not attachment.content_type or not attachment.content_type.startswith('image'):
            await interaction.response.send_message("❌ attachment is not an image", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        try:
            loop = asyncio.get_running_loop()
            await process_ocr_from_url(attachment.url, interaction, loop)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot):
    await bot.add_cog(OCRCommand(bot))