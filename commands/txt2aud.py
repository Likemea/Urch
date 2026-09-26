# Urch/commands/txt2aud.py
# DEPRECATED: The audio models have been removed
import discord
from discord import app_commands
from discord.ext import commands
import io
import time

from functions.audio_gen import generate_audio

class Txt2AudCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="txt2aud", description="Generate speech or music from text via Pollinations")
    @app_commands.describe(
        prompt="The text to generate audio/music for (max 4096 chars)",
        model="Audio model (nova-3 for speech, acestep for music)",
        voice="Voice preset to use (nova-3 speech only)",
        duration="Music duration in seconds, 3-60 (acestep music only)",
        style="Style/genre tags (acestep music only)",
        instrumental="Guarantees instrumental output (acestep music only)",
        speed="Speech speed, 0.25-4.0 (nova-3 speech only)",
        instruct="Emotion/style instruction (nova-3 speech only)",
        seed="Seed for reproducible results (-1 for random)"
    )
    @app_commands.choices(model=[
        app_commands.Choice(name="Speech (Nova 3)", value="nova-3"),
        app_commands.Choice(name="Music (AceStep)", value="acestep")
    ])
    @app_commands.choices(voice=[
        app_commands.Choice(name="Alloy", value="alloy"),
        app_commands.Choice(name="Echo", value="echo"),
        app_commands.Choice(name="Fable", value="fable"),
        app_commands.Choice(name="Onyx", value="onyx"),
        app_commands.Choice(name="Nova", value="nova"),
        app_commands.Choice(name="Shimmer", value="shimmer"),
        app_commands.Choice(name="Rachel", value="rachel"),
        app_commands.Choice(name="Adam", value="adam"),
        app_commands.Choice(name="Daniel", value="daniel"),
        app_commands.Choice(name="Sam", value="sam")
    ])
    async def txt2aud(
        self,
        interaction: discord.Interaction,
        prompt: str,
        model: str = "nova-3",
        voice: str = "alloy",
        duration: app_commands.Range[int, 3, 300] = 30,
        style: str = "",
        instrumental: bool = False,
        speed: app_commands.Range[float, 0.25, 4.0] = 1.0,
        instruct: str = "",
        seed: int = -1
    ):
        await interaction.response.defer(thinking=True)

        try:
            # Gather params based on model
            kwargs = {"seed": seed, "response_format": "mp3"}
            if model == "acestep":
                kwargs["duration"] = duration
                if style:
                    kwargs["style"] = style
                kwargs["instrumental"] = instrumental
            else:
                kwargs["speed"] = speed
                if instruct:
                    kwargs["instruct"] = instruct

            file = await generate_audio(
                text=prompt,
                model=model,
                voice=voice,
                **kwargs
            )

            if file:
                embed = discord.Embed(
                    title="🎵 Audio Result" if model == "nova-3" else "🎶 Music Result",
                    color=discord.Color.blue()
                )
                truncated_prompt = prompt if len(prompt) <= 1000 else f"{prompt[:997]}..."
                embed.add_field(name="Prompt", value=f"**{truncated_prompt}**", inline=False)
                
                model_name = "Speech (nova-3)" if model == "nova-3" else "Music (AceStep)"
                embed.add_field(name="Model", value=f"**{model_name}**", inline=True)
                
                footer_parts = []
                if seed != -1:
                    footer_parts.append(f"seed: {seed}")
                
                if model == "acestep":
                    embed.add_field(name="Duration", value=f"{duration}s", inline=True)
                    if style:
                        embed.add_field(name="Style", value=style, inline=True)
                    embed.add_field(name="Instrumental", value="Yes" if instrumental else "No", inline=True)
                else:
                    embed.add_field(name="Voice", value=voice, inline=True)
                    embed.add_field(name="Speed", value=f"{speed}x", inline=True)
                    if instruct:
                        embed.add_field(name="Emotion/Instruction", value=instruct, inline=True)
                
                if footer_parts:
                    embed.set_footer(text=" | ".join(footer_parts))
                    
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send("❌ Failed to generate audio. Please try again later.", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Txt2AudCommand(bot))
