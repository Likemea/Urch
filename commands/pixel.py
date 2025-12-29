# Urch/commands/pixel.py
import io
import random

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
from perlin_noise import PerlinNoise

class PixelCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pixel", description="Generate a 256x256 image of random pixels.")
    @app_commands.describe(seed="seed for the random number generator", size="Image resolution", palette="Color palette (random, grayscale, red, green, blue)", pattern="Pattern (random, stripes, gradient, noise)")
    async def pixel(self, interaction: discord.Interaction, seed: int = None, size: int = 256, palette: str = "random", pattern: str = "random"):
        if seed is None:
            seed = random.randint(0, 1000000)
        random.seed(seed)

        if size < 16 or size > 256:
            await interaction.response.send_message("Size must be between 16 and 256.", ephemeral=True)
            return

        img = Image.new('RGB', (size, size))
        pixels = img.load()

        if palette == "grayscale":
            colors = [(i, i, i) for i in range(256)]
        elif palette == "red":
            colors = [(i, 0, 0) for i in range(256)]
        elif palette == "green":
            colors = [(0, i, 0) for i in range(256)]
        elif palette == "blue":
            colors = [(0, 0, i) for i in range(256)]
        else:
            colors = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(256)]

        if pattern == "stripes":
            for i in range(size):
                color = random.choice(colors)
                for j in range(size):
                    pixels[i, j] = color
        elif pattern == "gradient":
            start_color = random.choice(colors)
            end_color = random.choice(colors)
            for i in range(size):
                for j in range(size):
                    r = start_color[0] + (end_color[0] - start_color[0]) * i // size
                    g = start_color[1] + (end_color[1] - start_color[1]) * j // size
                    b = start_color[2] + (end_color[2] - start_color[2]) * (i + j) // (2 * size)
                    pixels[i, j] = (r, g, b)
        elif pattern == "noise":
            noise = PerlinNoise(octaves=6, seed=seed)
            for i in range(size):
                for j in range(size):
                    x = i / size
                    y = j / size
                    n = noise([x, y])
                    color_value = int((n + 1) / 2 * 255)
                    pixels[i, j] = (color_value, color_value, color_value)
        else:
            for i in range(size):
                for j in range(size):
                    pixels[i, j] = random.choice(colors)

        with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename=f'{seed}.png')

        embed = discord.Embed(title="Generated Pixel Image", description="", color=0x00ff00)
        embed.add_field(name="Seed", value=f"**{seed}**", inline=True)
        embed.add_field(name="Size", value=f"**{size}x{size}**", inline=True)
        embed.add_field(name="Palette", value=f"**{palette}**", inline=True)
        embed.add_field(name="Pattern", value=f"**{pattern}**", inline=True)
        embed.set_image(url=f"attachment://{seed}.png")

        await interaction.response.send_message(embed=embed, file=file)

async def setup(bot):
    await bot.add_cog(PixelCommand(bot))