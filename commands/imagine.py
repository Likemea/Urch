# Urch/commands/imagine.py
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
import urllib.parse
import random

from functions.image_gen import generate_image
from providers import IMAGE_MODELS

class ImagineCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="imagine", description="Generate an image via Pollinations")
    @app_commands.describe(
        prompt="Description of the image",
        model="AI model to use",
        width="Width of the image",
        height="Height of the image",
        seed="Seed for reproducible results (-1 for random)",
        enhance="Urch prompt enhancement"
    )
    @app_commands.choices(model=[
        app_commands.Choice(name=info["disp"], value=mid) 
        for mid, info in IMAGE_MODELS.items()
    ])
    async def imagine(
        self, 
        interaction: discord.Interaction, 
        prompt: str, 
        model: str = "zimage",
        width: app_commands.Range[int, 128, 768] = 512,
        height: app_commands.Range[int, 128, 768] = 512,
        seed: int = -1,
        enhance: bool = False
    ):
        await interaction.response.defer(thinking=True)

        try:
            file = await generate_image(
                prompt=prompt, 
                model=model, 
                width=width, 
                height=height, 
                seed=seed,
                enhance=enhance
            )

            if file:
                embed = discord.Embed(
                    title="🎨 Image Result",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Prompt", value=f"**{prompt}**", inline=False)
                embed.add_field(name="Model", value=f"**{model}**", inline=False)
                embed.set_footer(text=f"{width}x{height} | {seed} | {enhance}")
                embed.set_image(url=f"attachment://{file.filename}")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send("❌ Failed to generate image. Please try again later.", ephemeral=True)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ImagineCommand(bot))