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
        # 1. Defer
        await interaction.response.defer(thinking=True)
        seed = random.randint(1,999999999)

        # 2. Prepare
        # URL-encode (e.g., "red cat" -> "red%20cat")
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Pollinations API URL struct
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # 3. Read
                        data = await response.read()
                        
                        # 4. Convert to Discord file-like obj
                        image_binary = io.BytesIO(data)
                        image_binary.seek(0)
                        
                        file = discord.File(fp=image_binary, filename="imagine.png")
                        
                        # 5. Create neat embed
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