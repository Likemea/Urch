# Urch/commands/filter.py
import io
import asyncio
import functools

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageFilter, ImageOps

from providers import get_session

MAX_AVATAR_BYTES = 8 * 1024 * 1024  # 8 MB cap


async def _read_bounded(response: aiohttp.ClientResponse, max_bytes: int) -> bytes | None:
    if getattr(response, "content_length", None) and response.content_length > max_bytes:
        return None
    content = getattr(response, "content", None)
    if content is not None and hasattr(content, "read"):
        data = await content.read(max_bytes + 1)
    else:
        data = await response.read()
    if len(data) > max_bytes:
        return None
    return data


class FilterCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def process_image(self, image_bytes: bytes, filter_type: str) -> io.BytesIO:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            if raw_img.width > 2048 or raw_img.height > 2048:
                raw_img.thumbnail((2048, 2048))
            image = raw_img.convert("RGB")

        if filter_type == "blur":
            image = image.filter(ImageFilter.GaussianBlur(radius=5))
        elif filter_type == "contour":
            image = image.filter(ImageFilter.CONTOUR)
        elif filter_type == "detail":
            image = image.filter(ImageFilter.DETAIL)
        elif filter_type == "edge_enhance":
            image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
        elif filter_type == "grayscale":
            image = ImageOps.grayscale(image)
        elif filter_type == "invert":
            image = ImageOps.invert(image)
        elif filter_type == "sepia":
            sepia = []
            r, g, b = (239, 224, 198)
            for i in range(256):
                sepia.extend((int(r * i / 255), int(g * i / 255), int(b * i / 255)))
            image = image.convert("L")
            image.putpalette(sepia)
            image = image.convert("RGB")
        elif filter_type == "posterize":
            image = ImageOps.posterize(image, 2)
        elif filter_type == "solarize":
            image = ImageOps.solarize(image, threshold=128)

        output_buffer = io.BytesIO()
        image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer

    @app_commands.command(name="filter", description="Apply a filter to an avatar or image")
    @app_commands.describe(user="User to filter", style="Filter to apply")
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Blur", value="blur"),
            app_commands.Choice(name="Contour", value="contour"),
            app_commands.Choice(name="Detail", value="detail"),
            app_commands.Choice(name="Edge Enhance", value="edge_enhance"),
            app_commands.Choice(name="Grayscale", value="grayscale"),
            app_commands.Choice(name="Invert", value="invert"),
            app_commands.Choice(name="Sepia", value="sepia"),
            app_commands.Choice(name="Posterize", value="posterize"),
            app_commands.Choice(name="Solarize", value="solarize"),
        ]
    )
    async def filter(
        self,
        interaction: discord.Interaction,
        style: app_commands.Choice[str],
        user: discord.User = None,
    ):
        await interaction.response.defer(thinking=True)

        target_user = user or interaction.user

        session = await get_session()
        async with session.get(
            target_user.display_avatar.url, timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                return await interaction.followup.send("Could not download avatar.")
            data = await _read_bounded(response, MAX_AVATAR_BYTES)
            if data is None:
                return await interaction.followup.send(
                    "❌ Avatar image is too large (maximum allowed size is 8 MB)."
                )

        loop = asyncio.get_running_loop()
        processed_buffer = await loop.run_in_executor(
            None, functools.partial(self.process_image, data, style.value)
        )

        file = discord.File(fp=processed_buffer, filename=f"{style.value}_{target_user.name}.png")
        await interaction.followup.send(
            f"**{target_user.display_name}** ({style.value})", file=file
        )


async def setup(bot):
    await bot.add_cog(FilterCommand(bot))
