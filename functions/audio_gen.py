# Urch/functions/audio_gen.py
import discord
import io
import aiohttp
import time
from providers import PROVIDERS

async def generate_audio(
    text: str,
    model: str = "nova-3",
    voice: str = "alloy",
    **kwargs
) -> discord.File:
    """Generates audio/music via Pollinations.ai (gen.pollinations.ai/v1/audio/speech) and returns a discord.File object"""
    api_key = PROVIDERS["pollinations"]["api_key"]
    url = "https://gen.pollinations.ai/v1/audio/speech"
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "input": text,
        "model": model,
        "response_format": kwargs.get("response_format", "mp3")
    }
    
    # Model-specific parameters
    if model == "acestep":
        # Music parameters
        if "duration" in kwargs and kwargs["duration"] is not None:
            payload["duration"] = kwargs["duration"]
        if "style" in kwargs and kwargs["style"]:
            payload["style"] = kwargs["style"]
        if "instrumental" in kwargs and kwargs["instrumental"] is not None:
            payload["instrumental"] = kwargs["instrumental"]
    else:
        # TTS parameters
        if voice:
            payload["voice"] = voice
        if "speed" in kwargs and kwargs["speed"] is not None:
            payload["speed"] = kwargs["speed"]
        if "instruct" in kwargs and kwargs["instruct"]:
            payload["instruct"] = kwargs["instruct"]
            
    if "seed" in kwargs and kwargs["seed"] is not None and kwargs["seed"] != -1:
        payload["seed"] = kwargs["seed"]
        
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.read()
                audio_binary = io.BytesIO(data)
                audio_binary.seek(0)
                
                # Default format to mp3 or whatever format was requested
                ext = kwargs.get("response_format", "mp3")
                return discord.File(fp=audio_binary, filename=f"gen_{int(time.time())}.{ext}")
            else:
                try:
                    err_json = await response.json()
                    print(f"[AudioGen] Failed with status {response.status}: {err_json}")
                except:
                    err_text = await response.text()
                    print(f"[AudioGen] Failed with status {response.status}: {err_text[:200]}")
                return None
