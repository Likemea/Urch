# Urch/commands/imagine.py
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
import urllib.parse
import random

class ImagineCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="imagine", description="Generate an image")
    @app_commands.describe(prompt="The description of the image you want to generate")
    async def imagine(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer(thinking=True)
        seed = random.randint(1,999999999)

        encoded_prompt = urllib.parse.quote(prompt)
        
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        
                        image_binary = io.BytesIO(data)
                        image_binary.seek(0)
                        
                        file = discord.File(fp=image_binary, filename="imagine.png")
                        
                        embed = discord.Embed(
                            title="",
                            description=f"**{prompt}**",
                            color=discord.Color.purple()
                        )
                        embed.set_image(url="attachment://imagine.png")
                        
                        await interaction.followup.send(embed=embed, file=file)
                    else:
                        await interaction.followup.send(f"❌ {response.status}")
                        
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")

async def setup(bot):
    await bot.add_cog(ImagineCommand(bot))