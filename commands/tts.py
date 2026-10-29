# Urch/commands/tts.py
import discord
from discord import app_commands
from discord.ext import commands

from functions.audio_gen import generate_audio, DEFAULT_VOICE, DEFAULT_MODEL
from safeguard import check_safeguard

VOICES = [
    ("Nova (Female, warm & natural)", "nova"),
    ("Alloy (Neutral, balanced)", "alloy"),
    ("Echo (Male, clear)", "echo"),
    ("Fable (British accent)", "fable"),
    ("Onyx (Male, deep & authoritative)", "onyx"),
    ("Shimmer (Female, expressive)", "shimmer"),
]


class TTSCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="tts",
        description="Turn text into speech",
    )
    @app_commands.describe(
        text="The text message to turn into speech",
        voice="The voice to use for speech",
        speed="Speaker speed (0.25 to 4.0, default 1.0)",
    )
    @app_commands.choices(
        voice=[app_commands.Choice(name=name, value=val) for name, val in VOICES]
    )
    async def tts(
        self,
        interaction: discord.Interaction,
        text: str,
        voice: str = DEFAULT_VOICE,
        speed: app_commands.Range[float, 0.25, 4.0] = 1.0,
    ):
        rl = getattr(self.bot, "rate_limiter", None)
        if rl:
            allowed, wait_time, reason = rl.check(str(interaction.user.id), tier="light")
            if not allowed:
                msg = (
                    reason
                    if wait_time <= 0
                    else f"⏳ Slow down! {reason} Try again in {wait_time:.1f}s."
                )
                await interaction.response.send_message(msg, ephemeral=True)
                return

        await interaction.response.defer(thinking=True)

        clean_text = text.strip()
        if not clean_text:
            await interaction.followup.send("❌ Please provide text to convert to speech.", ephemeral=True)
            return

        safeguard_func = getattr(self.bot, "check_safeguard", check_safeguard)
        try:
            safeguard_result = await safeguard_func([], clean_text, "")
            verdict = safeguard_result.get("verdict", "safe").lower()
            if verdict in ["unsafe_input", "unsafe_output", "unsafe_both"]:
                reason = safeguard_result.get("reasoning", "No specific reason provided.")
                policy = safeguard_result.get("violated_policy", "General Safety Policy")
                msg = (
                    f"🛡️ **Safeguard Block ({verdict})**\n"
                    f"- **Reason**: {reason}\n"
                    f"- **Violated Policy**: {policy}"
                )
                await interaction.followup.send(msg)
                return
        except Exception as e:
            print(f"[tts] Safeguard check error: {e}")

        try:
            file = await generate_audio(
                input_text=clean_text,
                voice=voice,
                speed=speed,
                model=DEFAULT_MODEL,
            )

            if file:
                preview = clean_text if len(clean_text) <= 100 else f"{clean_text[:97]}..."
                embed = discord.Embed(
                    title="🎙️ Output",
                    description=f"**Text:** {preview}",
                    color=discord.Color.teal(),
                )
                embed.add_field(name="Voice", value=voice, inline=True)
                embed.add_field(name="Speed", value=f"{speed}x", inline=True)
                embed.add_field(name="Model", value=DEFAULT_MODEL, inline=True)

                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(
                    "❌ Failed to generate speech. Please try again later.",
                    ephemeral=True,
                )
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TTSCommand(bot))
