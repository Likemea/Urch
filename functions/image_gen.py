# Urch/functions/image_gen.py
import discord
import urllib.parse
import io
import aiohttp
import time
from providers import PROVIDERS, get_session

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB cap


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


async def generate_image(
    prompt: str, model: str = "dreamshaper", width: int = 512, height: int = 512, **kwargs
) -> discord.File:
    """Generates an image via Pollinations.ai (gen.pollinations.ai) and returns a discord.File object"""
    encoded_prompt = urllib.parse.quote(prompt)
    base_url = PROVIDERS["pollinations"]["image_url"]
    api_key = PROVIDERS["pollinations"]["api_key"]

    url = f"{base_url}/{encoded_prompt}"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    params = {
        "model": model,
        "width": str(width),
        "height": str(height),
        "seed": str(kwargs.get("seed", -1)),
    }

    if kwargs.get("enhance"):
        params["enhance"] = "true"

    if kwargs.get("transparent"):
        params["transparent"] = "true"

    if kwargs.get("safe"):
        params["safe"] = str(kwargs["safe"]).lower()

    if kwargs.get("image"):
        params["image"] = kwargs["image"]

    if model == "gpt-image-2":
        params["quality"] = kwargs.get("quality", "low")

    session = await get_session()
    async with session.get(
        url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=120)
    ) as response:
        if response.status == 200:
            data = await _read_bounded(response, MAX_IMAGE_BYTES)
            if data is None:
                print("[ImageGen] Response exceeded maximum allowed size (10 MB)")
                return None
            image_binary = io.BytesIO(data)
            image_binary.seek(0)

            content_type = response.headers.get("Content-Type", "")
            ext = "jpg" if "jpeg" in content_type else "png"

            print(f"[ImageGen] {prompt}")
            return discord.File(fp=image_binary, filename=f"gen_{int(time.time())}.{ext}")
        else:
            print(f"[ImageGen] Failed with {response.status}")
            return None
