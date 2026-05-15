# Urch/functions/image_gen.py
import discord
import urllib.parse
import io
import aiohttp
import time
from providers import PROVIDERS

async def generate_image(prompt: str, model: str = "zimage", width: int = 512, height: int = 512, **kwargs) -> discord.File:
    """Generates an image via Pollinations.ai (gen.pollinations.ai) and returns a discord.File object"""
    encoded_prompt = urllib.parse.quote(prompt)
    base_url = PROVIDERS["pollinations"]["image_url"]
    api_key = PROVIDERS["pollinations"]["api_key"]
    
    url = f"{base_url}/{encoded_prompt}"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    params = {
        "model": model,
        "width": str(width),
        "height": str(height),
        "seed": str(kwargs.get("seed", -1)),
        "enhance": str(kwargs.get("enhance", False)).lower(),
        "negative_prompt": kwargs.get("negative_prompt", ""),
        "safe": kwargs.get("safe", ""),
        "quality": kwargs.get("quality", "medium"),
        "image": kwargs.get("image", ""),
        "transparent": str(kwargs.get("transparent", False)).lower(),
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.read()
                image_binary = io.BytesIO(data)
                image_binary.seek(0)
                
                # Determine extension based on content type or default to png
                content_type = response.headers.get("Content-Type", "")
                ext = "jpg" if "jpeg" in content_type else "png"
                
                return discord.File(fp=image_binary, filename=f"gen_{int(time.time())}.{ext}")
            else:
                print(f"[ImageGen] Failed with status {response.status}")
                return None