# Urch/functions/audio_gen.py
import asyncio
import io
import time
from typing import Optional
import aiohttp
import discord
from providers import PROVIDERS, get_session

TTS_API_URL = "https://gen.pollinations.ai/v1/audio/speech"
DEFAULT_VOICE = "nova"
DEFAULT_MODEL = "openai/tts-1"
MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15 MB cap


async def _read_bounded(response: aiohttp.ClientResponse, max_bytes: int) -> Optional[bytes]:
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


async def generate_audio(
    input_text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    model: str = DEFAULT_MODEL,
) -> Optional[discord.File]:
    """
    Generates speech audio via Pollinations (OpenAI-compatible /v1/audio/speech endpoint)
    and returns a discord.File object.
    """
    api_key = PROVIDERS.get("pollinations", {}).get("api_key")

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        speed = float(speed)
    except (ValueError, TypeError):
        speed = 1.0
    speed = max(0.25, min(4.0, speed))

    if len(input_text) > 500:
        input_text = input_text[:500]

    payload = {
        "model": model,
        "input": input_text,
        "voice": voice or DEFAULT_VOICE,
        "speed": speed,
    }

    session = await get_session()
    try:
        async with session.post(
            TTS_API_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as response:
            if response.status == 200:
                data = await _read_bounded(response, MAX_AUDIO_BYTES)
                if data is None:
                    print("[AudioGen] Response exceeded maximum allowed size (15 MB)")
                    return None
                audio_binary = io.BytesIO(data)
                audio_binary.seek(0)

                content_type = response.headers.get("Content-Type", "")
                ext = "mp3"
                if "wav" in content_type:
                    ext = "wav"
                elif "ogg" in content_type:
                    ext = "ogg"
                elif "aac" in content_type:
                    ext = "aac"
                elif "flac" in content_type:
                    ext = "flac"

                return discord.File(fp=audio_binary, filename=f"tts_{int(time.time())}.{ext}")
            else:
                err_text = await response.text()
                print(f"[AudioGen] Failed with status {response.status}: {err_text}")
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        print(f"[AudioGen] Request failed: {e!r}")
        return None
