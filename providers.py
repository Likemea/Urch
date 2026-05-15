# Urch/providers.py
"""
Provider-agnostic inference layer for Urch.
Supports Groq and Pollinations.ai (gen.pollinations.ai unified API).
All providers expose an OpenAI-compatible /v1/chat/completions endpoint.
"""

import os
import asyncio
import aiohttp
import json

# ── Provider Registry ─────────────────────────────────────────────────────────
PROVIDERS: dict = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key": os.environ.get("GROQ_API_KEY", ""),
    },
    "pollinations": {
        "url": "https://gen.pollinations.ai/v1/chat/completions",
        "image_url": "https://gen.pollinations.ai/image",
        "api_key": os.environ.get("POLLINATIONS_API_KEY", ""),
    },
}

# ── Image Model Registry ──────────────────────────────────────────────────────
IMAGE_MODELS: dict = {
    "flux": {
        "id": "flux", 
        "disp": "Flux Schnell",
        "routable": True,
        "router_info": "Legacy model; very fast but may not be coherent. Bad for text. Supports negative prompts."
    },
    "zimage": {
        "id": "zimage", 
        "disp": "Z-Image Turbo",
        "routable": True,
        "router_info": "Fast and versatile default model. Good for all-around use cases. Has a decent sense of text, but not great. Supports negative prompts."
    },
    "gptimage": {
        "id": "gptimage", 
        "disp": "GPT Image 1 Mini",
        "routable": True,
        "router_info": "DALL-E style model. Good for artistic, stylized, and creative concepts. High consistency."
    },
    "gptimage-large": {
        "id": "gptimage-large", 
        "disp": "GPT Image 1.5",
        "routable": False,
        "router_info": "Large version of GPT Image. Best for complex artistic prompts requiring high detail."
    },
    "wan-image": {
        "id": "wan-image", 
        "disp": "Wan 2.7 Image",
        "routable": False,
        "router_info": "Specialized model for cinematic, dramatic, and atmospheric visuals."
    },
    "qwen-image": {
        "id": "qwen-image", 
        "disp": "Qwen Image Plus",
        "routable": False,
        "router_info": "Optimized for anime, digital art, and illustration styles."
    },
    "klein": {
        "id": "klein", 
        "disp": "FLUX.2 Klein 4B",
        "routable": False,
        "router_info": "Minimalist and clean aesthetic. Good for logos, icons, and simple designs."
    },
    "kontext": {
        "id": "kontext", 
        "disp": "FLUX.1 Kontext",
        "routable": False,
        "router_info": "Experimental model. Best for abstract and conceptual art. Bad for text."
    },
}
# ── Model Registry ────────────────────────────────────────────────────────────
# Capability flags control payload sanitization — no unsupported fields are
# ever sent. extra_params are merged in before sanitization (always supported).
#
# Fields:
#   id               – Exact model ID sent to the API
#   disp             – Human-readable display name (settings UI)
#   provider         – Key in PROVIDERS
#   vision           – Accepts image_url in messages
#   reasoning_effort – Accepts reasoning_effort param
#   tools            – Accepts tools / tool_choice params
#   response_format  – Accepts response_format param
#   routable         – Eligible for automatic model routing
#   extra_params     – Extra payload fields always injected for this model
MODELS: dict = {
    # ── Groq ─────────────────────────────────────────────────────────────────
    "l3.1-8b": {
        "id": "llama-3.1-8b-instant",
        "disp": "Llama 3.1 8B",
        "provider": "groq",
        "vision": False,
        "reasoning_effort": False,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Lowest weight. Best for quick responses, chit-chat, simple Q&A, greetings, and nonsensical inputs.",
    },
    "gpt-oss-20b": {
        "id": "openai/gpt-oss-20b",
        "disp": "GPT OSS 20B",
        "provider": "groq",
        "vision": False,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "extra_params": {"reasoning_effort": "low"},
        "router_info": "Low-Medium weight. Features Chain-of-Thought (CoT) reasoning. Good for intermediate complexity and multi-step problem solving.",
    },
    "gpt-oss-120b": {
        "id": "openai/gpt-oss-120b",
        "disp": "GPT OSS 120B",
        "provider": "groq",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "extra_params": {
            "reasoning_effort": "medium",
            "tools": [{"type": "code_interpreter"}],
        },
        "router_info": "Medium-High weight. Advanced complexity, native tool calling, and extended CoT. Ideal for agentic workflows.",
    },
    "l4-17": {
        "id": "meta-llama/llama-4-scout-17b-16e-instruct",
        "disp": "Llama 4 Scout",
        "provider": "groq",
        "vision": True,
        "reasoning_effort": False,
        "tools": False,
        "response_format": False,
        "routable": True,
        "router_info": "Medium weight. Supports vision. Good for image analysis and tasks that require visual input.",
    },
    "q32": {
        "id": "qwen/qwen3-32b",
        "disp": "Qwen3 32B",
        "provider": "groq",
        "vision": False,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": False,
        "extra_params": {"reasoning_effort": "none"},
        "router_info": "",
    },

    # ── Pollinations ──────────────────────────────────────────────────────────
    "gpt-5.4-nano": {
        "id": "openai",
        "disp": "GPT-5.4 Nano",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": False,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Lowest weight. Efficient and reliable model for general tasks. It's very fast and supports vision.",
    },
    "n-m": {
        "id": "nova-fast",
        "disp": "Nova Micro",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": False,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Extremely fast and lightweight model for simple, low-complexity interactions.",
    },
    "n2-l": {
        "id": "nova",
        "disp": "Nova 2 Lite",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Small and fast model. Suitable for analytical queries. Supports reasoning.",
    },
    "q3-c": {
        "id": "qwen-coder",
        "disp": "Qwen3 Coder 30B",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Fast, specialized coding model.",
    },
    "q3-v": {
        "id": "qwen-vision",
        "disp": "Qwen3 VL 30B A3B Thinking",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Multimodal model that supports reasoning. Good for efficient image analyses.",
    },
    "p-s": {
        "id": "perplexity-fast",
        "disp": "Perplexity Sonar",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low-medium weight. Fast, specialized search engine model. Best for up-to-date knowledge and information.",
    },
    "gemini-2.5-flash-lite": {
        "id": "gemini-fast",
        "disp": "Gemini 2.5 Flash Lite",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": False,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low-medium weight. Very fast, multimodal model, also surprisingly capable. Supports vision and tool use.",
    },
    "m3.1-s": {
        "id": "mistral",
        "disp": "Mistral Small 3.1",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": False,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Low-medium weight. Compact and efficient model for standard conversational tasks. Supports vision.",
    },
    "grok-4.20": {
        "id": "grok",
        "disp": "Grok 4.20 Non-reasoning",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": False,
        "tools": False,
        "response_format": False,
        "routable": True,
        "router_info": "Medium-high weight. Powerful general-purpose model with broad knowledge, Grok is known for its rebellious, quirky personality. Supports vision.",
    },
    "m3-l": {
        "id": "mistral-large",
        "disp": "Mistral Large 3",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Medium-high weight. High-performance model with advanced reasoning for complex logical tasks. Supports vision and reasoning.",
    },
    "mx2.7": {
        "id": "minimax",
        "disp": "Minimax M2.7",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "Medium-high weight. High-performance model with advanced reasoning for complex logical tasks. Supports reasoning.",
    },
    "k2.5": {
        "id": "kimi",
        "disp": "Kimi K2.5",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": False,
        "response_format": True,
        "routable": True,
        "router_info": "High weight. Sophisticated model with long-context reasoning and multimodal input support. Supports vision and reasoning.",
    },
}

# ── Payload Sanitizer ─────────────────────────────────────────────────────────
_CAPABILITY_FIELDS = {
    "reasoning_effort": "reasoning_effort",
    "tools": "tools",
    "response_format": "response_format",
}

def sanitize_payload(payload: dict, caps: dict) -> dict:
    """
    Returns a clean copy of payload with unsupported fields stripped based on
    the capability flags in `caps`. `caps` mirrors a MODELS entry or an ad-hoc
    dict with boolean capability keys.
    """
    clean = dict(payload)

    # Always ensure model ID comes from caps if available
    if "id" in caps:
        clean["model"] = caps["id"]

    # Apply extra_params first (they are always valid for this model)
    for k, v in caps.get("extra_params", {}).items():
        clean.setdefault(k, v)

    # Strip fields the model doesn't support
    for cap_key, payload_key in _CAPABILITY_FIELDS.items():
        if not caps.get(cap_key, False):
            clean.pop(payload_key, None)
            if payload_key == "tools":
                clean.pop("tool_choice", None)

    return clean

# ── Low-level HTTP ────────────────────────────────────────────────────────────
async def _post(provider_key: str, payload: dict, timeout: int = 20, stream: bool = False):
    """Single POST to a provider. Raises on HTTP/connection errors."""
    cfg = PROVIDERS[provider_key]
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    
    # We use a longer timeout for streaming connections
    total_timeout = 60 if stream else timeout
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            cfg["url"], headers=headers, json=payload,
            timeout=aiohttp.ClientTimeout(total=total_timeout)
        ) as resp:
            resp.raise_for_status()
            if stream:
                return resp 
            return await resp.json()

# ── User-facing Model Call ────────────────────────────────────────────────────
FALLBACK_MODEL_KEY = "l3.1-8b"  # llama-3.1-8b-instant on Groq

async def call_provider(model_key: str, payload: dict, retries: int = 2) -> tuple:
    """
    Call the provider for `model_key` with retry logic.
    On total failure, falls back to FALLBACK_MODEL_KEY non-interruptingly.
    Returns (response_json, model_id_used).
    """
    model_info = MODELS.get(model_key, MODELS[FALLBACK_MODEL_KEY])
    clean = sanitize_payload(payload, model_info)
    provider_key = model_info["provider"]

    for attempt in range(retries):
        try:
            resp = await _post(provider_key, clean)
            return resp, model_info["id"]
        except Exception as e:
            print(f"[Provider] Attempt {attempt + 1}/{retries} failed "
                  f"for {model_info['id']} ({provider_key}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 + attempt * 2)

    # Hard fallback
    fallback = MODELS[FALLBACK_MODEL_KEY]
    print(f"⚠️ All retries exhausted. Falling back to {fallback['id']}")
    fallback_payload = sanitize_payload({
        "messages": payload.get("messages", []),
        "temperature": payload.get("temperature", 0.7),
        "top_p": payload.get("top_p", 0.4),
        "max_completion_tokens": payload.get("max_completion_tokens", 512),
    }, fallback)
    try:
        resp = await _post(fallback["provider"], fallback_payload)
        return resp, fallback["id"]
    except Exception as e:
        print(f"[Provider] Fallback also failed: {e}")
        raise

# ── Internal / Infrastructure Model Call ────────────────────────────────────
async def call_model_direct(
    provider_key: str,
    model_id: str,
    payload: dict,
    caps: dict = None,
    timeout: int = 20,
    retries: int = 2,
) -> dict:
    """
    Direct provider call for internal infrastructure models (router, agentic
    planner, safeguard) that are not in the user-facing MODELS registry.
    `caps` is an optional capability dict for payload sanitization.
    Returns the raw response JSON. Raises on total failure.
    """
    clean = dict(payload)
    clean["model"] = model_id
    if caps:
        # Merge extra_params and strip unsupported fields
        for k, v in caps.get("extra_params", {}).items():
            clean.setdefault(k, v)
        for cap_key, payload_key in _CAPABILITY_FIELDS.items():
            if not caps.get(cap_key, False):
                clean.pop(payload_key, None)
                if payload_key == "tools":
                    clean.pop("tool_choice", None)

    last_exc = None
    for attempt in range(retries):
        try:
            return await _post(provider_key, clean, timeout=timeout)
        except Exception as e:
            last_exc = e
            print(f"[Provider:Direct] Attempt {attempt + 1}/{retries} "
                  f"failed for {model_id} ({provider_key}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(1 + attempt)

    raise last_exc

# ── Streaming Model Call ──────────────────────────────────────────────────────
async def call_provider_stream(model_key: str, payload: dict, retries: int = 2):
    """
    Call the provider for `model_key` and yield text chunks.
    Automatically handles sanitization and 'stream': True payload.
    """
    model_info = MODELS.get(model_key, MODELS[FALLBACK_MODEL_KEY])
    clean = sanitize_payload(payload, model_info)
    clean["stream"] = True
    provider_key = model_info["provider"]
    cfg = PROVIDERS[provider_key]
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    cfg["url"], headers=headers, json=clean,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.content:
                        line_text = line.decode('utf-8').strip()
                        if not line_text:
                            continue
                        if line_text.startswith("data: "):
                            data_str = line_text[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                if "choices" in chunk and chunk["choices"]:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            return # Success
        except Exception as e:
            print(f"[Provider:Stream] Attempt {attempt + 1}/{retries} failed "
                  f"for {model_info['id']} ({provider_key}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(1 + attempt)
            else:
                raise