# Urch/functions/image_gen.py
import discord
import urllib.parse
import io
import aiohttp
import time

async def generate_image(prompt: str) -> discord.File:
    """Generates an image via Pollinations.ai and returns a discord.File object"""
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                image_binary = io.BytesIO(data)
                image_binary.seek(0)
                return discord.File(fp=image_binary, filename=f"gen_{int(time.time())}.png")
            else:
                return None