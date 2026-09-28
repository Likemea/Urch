# Urch/providers.py
"""
Provider-agnostic inference layer for Urch.
Supports Groq and Pollinations.ai (gen.pollinations.ai unified API).
All providers expose an OpenAI-compatible /v1/chat/completions endpoint.
"""

import asyncio
import aiohttp
import json
import config
from typing import Optional


class ProviderClientError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Client error {status}: {message}")


# ── Provider Registry ─────────────────────────────────────────────────────────
PROVIDERS: dict = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key": config.GROQ_API_KEY,
    },
    "pollinations": {
        "url": "https://gen.pollinations.ai/v1/chat/completions",
        "image_url": "https://gen.pollinations.ai/image",
        "api_key": config.POLLINATIONS_API_KEY,
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "api_key": config.GOOGLE_API_KEY,
    },
}

# ── Image Model Registry ──────────────────────────────────────────────────────
IMAGE_MODELS: dict = {
    "dreamshaper": {
        "id": "dreamshaper",
        "disp": "DreamShaper 8 LCM",
        "routable": True,
        "router_info": "Default. Ultra-fast, Ultra-low-cost image generation.",
    },
    "flux": {
        "id": "flux",
        "disp": "Flux Schnell",
        "routable": False,
        "router_info": "Legacy model; very fast but may not be coherent. Bad for text.",
    },
    "zimage": {
        "id": "zimage",
        "disp": "Z-Image Turbo",
        "routable": False,
        "router_info": "Fast and versatile model. Good for all-around use cases. Has a decent sense of text, but not great.",
    },
    "gptimage": {
        "id": "gptimage",
        "disp": "GPT Image 1 Mini",
        "routable": False,
        "router_info": "DALL-E style model. Good for artistic, stylized, and creative concepts. High consistency.",
    },
    "gpt-image-2": {
        "id": "gpt-image-2",
        "disp": "GPT Image 2",
        "routable": False,
        "router_info": "The most powerful image model.",
    },
    "klein": {
        "id": "klein",
        "disp": "FLUX.2 Klein 4B",
        "routable": False,
        "router_info": "Minimalist and clean aesthetic. Good for logos, icons, and simple designs.",
    },
    "kontext": {
        "id": "kontext",
        "disp": "FLUX.1 Kontext",
        "routable": False,
        "router_info": "Experimental model. Best for abstract and conceptual art. Bad for text.",
    },
}
# ── Model Registry ────────────────────────────────────────────────────────────
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
    "gpt-oss-20b": {
        "id": "openai/gpt-oss-20b",
        "disp": "GPT OSS 20B",
        "provider": "groq",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low-Medium weight. Features Chain-of-Thought (CoT) reasoning. Good for intermediate complexity and multi-step problem solving. Can think and use tools.",
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
        "router_info": "Medium-High weight. Advanced complexity, native tool calling, and extended CoT. Ideal for agentic workflows. Can think and use tools.",
    },
    "qwen3.8-27b": {
        "id": "qwen/qwen3.8-27b",
        "disp": "Qwen3.8 27B",
        "provider": "groq",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Medium-High weight. Alibaba's best open source model. Fast, cheap, and versatile. Can see, think, and use tools.",
    },
    # ── Pollinations ──────────────────────────────────────────────────────────
    "llama3.1-8b": {
        "id": "community/ZapGaming/llama3.1-8b-xturbo",
        "disp": "Llama 3.1 8B",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": False,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. 1K+ tokens per second. Extremely useless at everything except pretending to chat",
    },
    "muse-glimmer": {
        "id": "vendouple/muse-glimmer-30b:free",
        "disp": "Muse Glimmer",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Meta's open-weight agentic model. Can see, think, and use tools.",
    },
    "ministral-3-14b": {
        "id": "mikl-shortcuts/ministral-3",
        "disp": "Ministral 3 14B",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": False,
        "tools": False,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Mistral's open-source lightweight model. Decent all-rounder. Can see.",
    },
    "gemini-2.5-flash": {
        "id": "community/AkshayCoder48/gemini-2.5-flash",
        "disp": "Gemini 2.5 Flash",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Google's legacy Flash model. Optimized for conversation. Can think and use tools.",
    },
    "gpt-4o": {
        "id": "community/AkshayCoder48/gpt-4o-latest",
        "disp": "GPT-4o",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. The all-round workhorse for chat, writing and coding. Can use tools.",
    },
    "deepseek-v3": {
        "id": "community/AkshayCoder48/deepseek-v3",
        "disp": "Deepseek V3",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Efficient 685B MoE workhorse for chat, coding, and tool use. Can think and use tools.",
    },
    "step-3.7-flash": {
        "id": "community/AkshayCoder48/step-3.7-flash",
        "disp": "Step 3.7 Flash",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Fast StepFun model for high-volume chat and tool-calling workloads. No refusals on creative or edgy prompts. Can use tools.",
    },
    "laguna-s2.1": {
        "id": "YoannDev90/poolside-laguna-s-2.1:free",
        "disp": "Laguna S 2.1",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Poolside's open-source lightweight model. Optimized for conversation. Can think and use tools.",
    },
    "nova-micro": {
        "id": "nova-fast",
        "disp": "Nova Micro",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": False,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Extremely fast and lightweight model for simple, low-complexity interactions. Can use tools.",
    },
    "nemotron-3.5-lightning": {
        "id": "nemotron-3.5-lightning",
        "disp": "Nemotron 3.5 Lightning",
        "provider": "pollinations",
        "vision": False,
        "reasoning_effort": True,
        "tools": True,
        "response_format": False,
        "routable": True,
        "router_info": "Lowest weight. Fast open-weight reasoning for high-volume agent tasks, tool use and structured output. Can use tools.",
    },
    "gpt-5.4-nano": {
        "id": "openai",
        "disp": "GPT-5.4 Nano",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Efficient and reliable model for general tasks. Can see, think, and use tools.",
    },
    "glm-5.3-flash": {
        "id": "z-ai/glm-5.3-flash",
        "disp": "GLM 5.3 Flash",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Zhipu's lightweight flagship designed for coding and agentic tasks. Can see, think, and use tools.",
    },
    "deepseek-v4.1-flash": {
        "id": "deepseek/deepseek-v4.1-flash",
        "disp": "Deepseek V4.1 Flash",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low-medium weight. Frontier reasoning & coding. Can see, think, and use tools.",
    },
    "gpt-5.6-luna": {
        "id": "gpt-5.6-luna",
        "disp": "GPT-5.6 Luna",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Medium weight. Well-rounded, cheap and fast model with good agentic capabilities. Can see, think, and use tools.",
    },
    "minimax": {
        "id": "minimax",
        "disp": "Minimax M3",
        "provider": "pollinations",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Medium-high weight. Coding, agentic & multi-language. 1M context reasoning. Can see, think, and use tools.",
    },
    # ── Google AI Studio ──────────────────────────────────────────────────────
    "gemma-4-26b-a4b-it": {
        "id": "gemma-4-26b-a4b-it",
        "disp": "Gemma 4 26B A4B IT",
        "provider": "google",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. A Mixture-of-Experts model that activates only 4B parameters per inference, delivering high-performance reasoning with a fraction of the memory cost — ideal for cost-efficient, high-throughput server deployments. Can see, think, and use tools.",
    },
    "gemma-4-31b-it": {
        "id": "gemma-4-31b-it",
        "disp": "Gemma 4 31B IT",
        "provider": "google",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low weight. Google DeepMind's flagship open-weight dense model, purpose-built for maximum quality in data center environments with a 256K context window and advanced long-context architecture. Can see, think, and use tools.",
    },
    "gemini-3.5-flash-lite": {
        "id": "gemini-3.5-flash-lite",
        "disp": "Gemini 3.5 Flash Lite",
        "provider": "google",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "Low-medium weight. Ultra-lightweight and extremely fast, optimized for high-volume agentic tasks, translation, and simple data processing. Can see, think, and use tools.",
    },
    "gemini-3.8-flash": {
        "id": "gemini-3.8-flash",
        "disp": "Gemini 3.8 Flash",
        "provider": "google",
        "vision": True,
        "reasoning_effort": True,
        "tools": True,
        "response_format": True,
        "routable": True,
        "router_info": "High weight. Google's most intelligent model for sustained frontier performance in agentic and coding tasks. Can see, think, and use tools.",
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

    if "id" in caps:
        clean["model"] = caps["id"]

    # apply extra_params first (they are always valid for this model)
    for k, v in caps.get("extra_params", {}).items():
        clean.setdefault(k, v)

    # strip fields the model doesn't support
    for cap_key, payload_key in _CAPABILITY_FIELDS.items():
        if not caps.get(cap_key, False):
            clean.pop(payload_key, None)
            if payload_key == "tools":
                clean.pop("tool_choice", None)

    # never force json_object mode when using native tool calling
    if clean.get("tools"):
        clean.pop("response_format", None)

    if clean.get("reasoning_effort") == "Auto":
        clean.pop("reasoning_effort", None)

    # sanitize message history based on tool capability
    if "messages" in clean and isinstance(clean["messages"], list):
        sanitized_messages = []
        supports_tools = caps.get("tools", False)
        for msg in clean["messages"]:
            if not isinstance(msg, dict):
                sanitized_messages.append(msg)
                continue

            msg_copy = dict(msg)
            role = msg_copy.get("role")

            if not supports_tools:
                # if model doesn't support tools, convert tool output messages to user role
                if role == "tool":
                    tool_name = msg_copy.get("name", "tool")
                    tool_content = msg_copy.get("content", "")
                    sanitized_messages.append(
                        {
                            "role": "user",
                            "content": f"[Tool Result for {tool_name}]:\n{tool_content}",
                        }
                    )
                    continue
                elif role == "assistant" and "tool_calls" in msg_copy:
                    # strip tool_calls and put example text if content is empty
                    calls = msg_copy.pop("tool_calls", [])
                    if not msg_copy.get("content"):
                        names = ", ".join(
                            [
                                c.get("function", {}).get("name", "")
                                for c in calls
                                if isinstance(c, dict)
                            ]
                        )
                        msg_copy["content"] = f"[Invoked tools: {names}]"

            sanitized_messages.append(msg_copy)
        clean["messages"] = sanitized_messages

    return clean


# ── Global HTTP Session ───────────────────────────────────────────────────────
_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    """Get the shared, global aiohttp.ClientSession."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_session():
    """Gracefully close the global aiohttp.ClientSession."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


# ── Low-level HTTP ────────────────────────────────────────────────────────────
async def _post(provider_key: str, payload: dict, timeout: int = 20):
    """Single POST to a provider. Raises on HTTP/connection errors."""
    cfg = PROVIDERS[provider_key]
    headers = {
        "Content-Type": "application/json",
    }
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    session = await get_session()
    async with session.post(
        cfg["url"], headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)
    ) as resp:
        if 400 <= resp.status < 500:
            body = await resp.text()
            raise ProviderClientError(resp.status, body)
        resp.raise_for_status()
        return await resp.json()


# ── User-facing Call ────────────────────────────────────────────────────
FALLBACK_MODEL_KEY = "llama3.1-8b"


async def call_provider(model_key: str, payload: dict, retries: int = 2) -> tuple:
    """
    call the provider for `model_key` with retry and fallback logic.
    supports a 3-stage fallback flow:
      1. normal payload (sanitized) for the selected model.
      2. if 4xx error occurs, retry immediately with stripped custom parameters (no temperature, top_p, reasoning_effort, max_completion_tokens).
      3. if that also fails, fallback to FALLBACK_MODEL_KEY
    returns (response_json, model_id_used)
    """
    model_info = MODELS.get(model_key, MODELS[FALLBACK_MODEL_KEY])
    provider_key = model_info["provider"]
    clean = sanitize_payload(payload, model_info)

    # stage 1 - normal
    for attempt in range(retries):
        try:
            resp = await _post(provider_key, clean)
            return resp, model_info["id"]
        except ProviderClientError as pce:
            print(
                f"[Provider] 4xx Client Error ({pce.status}) on attempt {attempt + 1}/{retries} "
                f"for {model_info['id']} ({provider_key}): {pce.message}"
            )
            break
        except Exception as e:
            print(
                f"[Provider] Attempt {attempt + 1}/{retries} failed "
                f"for {model_info['id']} ({provider_key}): {e}"
            )
            if attempt < retries - 1:
                await asyncio.sleep(2 + attempt * 2)
            else:
                break

    # stage 2 - no params
    print(f"[Provider] Retrying {model_info['id']} with stripped parameters...")
    stripped_payload = dict(payload)
    for k in ["temperature", "top_p", "reasoning_effort", "max_completion_tokens"]:
        stripped_payload.pop(k, None)
    clean_stripped = sanitize_payload(stripped_payload, model_info)
    try:
        resp = await _post(provider_key, clean_stripped)
        return resp, model_info["id"]
    except Exception as e:
        print(f"[Provider] Stripped parameters retry failed for {model_info['id']}: {e}")

    # stage 3 - fallback
    fallback = MODELS[FALLBACK_MODEL_KEY]
    print(f"⚠️ All stages failed. Falling back to {fallback['id']}")
    fallback_payload = sanitize_payload(
        {
            "messages": payload.get("messages", []),
            "temperature": 0.7,
            "top_p": 0.4,
            "max_completion_tokens": 1000,
        },
        fallback,
    )
    try:
        resp = await _post(fallback["provider"], fallback_payload)
        return resp, fallback["id"]
    except Exception as e:
        print(f"[Provider] Fallback also failed: {e}")
        raise


# ── Internal Call ────────────────────────────────────
async def call_model_direct(
    provider_key: str,
    model_id: str,
    payload: dict,
    caps: dict = None,
    timeout: int = 20,
    retries: int = 2,
) -> dict:
    """
    direct provider call for internal infrastructure models (router, agentic
    planner, safeguard) that are not in the user-facing MODELS registry.
    `caps` is an optional capability dict for payload sanitization.
    returns the raw response JSON. raises on total failure
    """
    clean = dict(payload)
    clean["model"] = model_id
    if caps:
        # merge extra_params and strip unsupported fields
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
            print(
                f"[Provider:Direct] Attempt {attempt + 1}/{retries} "
                f"failed for {model_id} ({provider_key}): {e}"
            )
            if attempt < retries - 1:
                await asyncio.sleep(1 + attempt)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Direct model call failed with 0 retries configured for {model_id}")


# ── Streaming Call ──────────────────────────────────────────────────────
async def call_provider_stream(model_key: str, payload: dict, retries: int = 2):
    """
    call the provider for `model_key` and yield text chunks.
    on 4xx errors, retries with stripped params, then falls back
    """
    model_info = MODELS.get(model_key, MODELS[FALLBACK_MODEL_KEY])
    provider_key = model_info["provider"]
    clean = sanitize_payload(payload, model_info)
    clean["stream"] = True

    cfg = PROVIDERS[provider_key]
    headers = {
        "Content-Type": "application/json",
    }
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    session = await get_session()

    async def consume_stream(response):
        async for line in response.content:
            line_text = line.decode("utf-8").strip()
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

    # stage 1 - normal
    success = False
    for attempt in range(retries):
        try:
            async with session.post(
                cfg["url"], headers=headers, json=clean, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if 400 <= resp.status < 500:
                    body = await resp.text()
                    raise ProviderClientError(resp.status, body)
                resp.raise_for_status()
                async for chunk in consume_stream(resp):
                    yield chunk
                success = True
                return
        except ProviderClientError as pce:
            print(
                f"[Provider:Stream] 4xx Client Error ({pce.status}) on attempt {attempt + 1}/{retries}: {pce.message}"
            )
            break
        except Exception as e:
            print(f"[Provider:Stream] Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 + attempt * 2)

    # stage 2 - no params
    if not success:
        print(f"[Provider:Stream] Retrying {model_info['id']} with stripped parameters...")
        stripped_payload = dict(payload)
        for k in ["temperature", "top_p", "reasoning_effort", "max_completion_tokens"]:
            stripped_payload.pop(k, None)
        clean_stripped = sanitize_payload(stripped_payload, model_info)
        clean_stripped["stream"] = True
        try:
            async with session.post(
                cfg["url"],
                headers=headers,
                json=clean_stripped,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if 400 <= resp.status < 500:
                    body = await resp.text()
                    raise ProviderClientError(resp.status, body)
                resp.raise_for_status()
                async for chunk in consume_stream(resp):
                    yield chunk
                success = True
                return
        except Exception as e:
            print(f"[Provider:Stream] Stripped parameters retry failed for {model_info['id']}: {e}")

    # stage 3 - fallback
    if not success:
        fallback = MODELS[FALLBACK_MODEL_KEY]
        print(f"⚠️ [Provider:Stream] Falling back to {fallback['id']}")
        fallback_payload = sanitize_payload(
            {
                "messages": payload.get("messages", []),
                "temperature": 0.7,
                "top_p": 0.4,
                "max_completion_tokens": 1000,
            },
            fallback,
        )
        fallback_payload["stream"] = True

        f_cfg = PROVIDERS[fallback["provider"]]
        f_headers = {
            "Content-Type": "application/json",
        }
        if f_cfg.get("api_key"):
            f_headers["Authorization"] = f"Bearer {f_cfg['api_key']}"

        async with session.post(
            f_cfg["url"],
            headers=f_headers,
            json=fallback_payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()
            async for chunk in consume_stream(resp):
                yield chunk
