# Urch/commands/analyze.py
import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import config
from providers import get_session
from safeguard import check_safeguard

GROQ_API_KEY = config.GROQ_API_KEY
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}


async def generate_analysis(image_url: str, prompt: str, user_id: str) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]

    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 1024,
    }

    try:
        session = await get_session()
        async with session.post(
            GROQ_API_URL,
            headers=headers_groq,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            response_data = await resp.json()
            return response_data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error analyzing image: {str(e)}"


async def dispatch_analysis(interaction: Interaction, image_url: str, prompt: str, bot=None):
    user_id = str(interaction.user.id)
    response = await generate_analysis(image_url, prompt, user_id)

    safeguard_func = getattr(bot, "check_safeguard", check_safeguard) if bot else check_safeguard
    safeguard_result = await safeguard_func([], prompt, response)
    verdict = safeguard_result.get("verdict", "safe").lower()
    if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
        reason = safeguard_result.get("reasoning", "Unknown reason.")
        policy = safeguard_result.get("violated_policy", "Unspecified policy.")
        warning_text = (
            "Sorry, something went wrong. Please try again."
        )
        await interaction.followup.send(warning_text)
        return

    if len(response) > 1900:
        chunks = [response[i : i + 1900] for i in range(0, len(response), 1900)]
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)
    else:
        await interaction.followup.send(response)


class AnalyzeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.ctx_menu = app_commands.ContextMenu(
            name="Analyze Image", callback=self.analyze_context
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="analyze", description="Analyze an image")
    @app_commands.describe(
        file="The image to analyze", prompt="Specific question about the image (Optional)"
    )
    async def analyze_slash(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        prompt: str = "Describe this image in detail.",
    ):
        if not file.content_type or not file.content_type.startswith("image"):
            await interaction.response.send_message(
                "❌ Please upload a valid image file.", ephemeral=True
            )
            return

        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(
                str(interaction.user.id), model_id="qwen/qwen3.8-27b"
            )
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
            await dispatch_analysis(interaction, file.url, prompt, bot=self.bot)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")

    async def analyze_context(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message("❌ No image attachment found", ephemeral=True)
            return

        attachment = message.attachments[0]
        if not attachment.content_type or not attachment.content_type.startswith("image"):
            await interaction.response.send_message("❌ attachment is not an image", ephemeral=True)
            return

        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(
                str(interaction.user.id), model_id="qwen/qwen3.8-27b"
            )
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                await interaction.response.send_message(msg, ephemeral=True)
                return

        default_prompt = "Describe this image in detail."

        await interaction.response.defer(thinking=True)
        try:
            await dispatch_analysis(interaction, attachment.url, default_prompt, bot=self.bot)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot):
    await bot.add_cog(AnalyzeCommand(bot))
