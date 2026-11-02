# tests/ai/test_providers.py
"""
Tests for LLM model registries, image model registries, payload sanitization,
and vision routing.
"""

from unittest.mock import patch
import pytest

from systems.ai.providers import (
    FALLBACK_MODEL_KEY,
    IMAGE_MODELS,
    MODELS,
    PROVIDERS,
    sanitize_payload,
)

REQUIRED_MODEL_FIELDS = {
    "id",
    "disp",
    "provider",
    "vision",
    "reasoning_effort",
    "tools",
    "response_format",
    "routable",
}


def test_models_have_required_fields():
    assert FALLBACK_MODEL_KEY in MODELS, "Fallback model key missing from MODELS"

    for key, entry in MODELS.items():
        missing = REQUIRED_MODEL_FIELDS - set(entry)
        assert not missing, f"MODELS['{key}'] missing fields: {missing}"


def test_models_use_known_providers():
    for key, entry in MODELS.items():
        assert entry["provider"] in PROVIDERS, (
            f"MODELS['{key}'] uses unknown provider '{entry['provider']}'"
        )


def test_routable_models_have_router_info():
    for key, entry in MODELS.items():
        if entry.get("routable"):
            assert entry.get("router_info"), f"Routable model '{key}' has no router_info"


def test_image_models_well_formed():
    for key, entry in IMAGE_MODELS.items():
        assert "id" in entry, f"IMAGE_MODELS['{key}'] missing id"
        assert "disp" in entry, f"IMAGE_MODELS['{key}'] missing disp"


def test_agent_sanitize_gpt_oss_reasoning():
    """Verify sanitize_payload pops reasoning_effort: 'none' for gpt-oss models."""
    caps = {"reasoning_effort": True}
    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": "hello"}],
        "reasoning_effort": "none",
    }
    cleaned = sanitize_payload(payload, caps)
    assert "reasoning_effort" not in cleaned

    payload_low = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": "hello"}],
        "reasoning_effort": "low",
    }
    cleaned_low = sanitize_payload(payload_low, caps)
    assert cleaned_low["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_vision_payload_sanitization_and_routing():
    """Verifies that non-vision models have multimodal content flattened, and router prompts include [Vision]."""
    import main as main_mod

    fallback_caps = MODELS[FALLBACK_MODEL_KEY]
    assert fallback_caps.get("vision") is False

    multimodal_payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image:"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}},
                ],
            }
        ]
    }

    sanitized = sanitize_payload(multimodal_payload, fallback_caps)
    flattened_msg = sanitized["messages"][0]["content"]
    assert isinstance(flattened_msg, str)
    assert "Describe this image:" in flattened_msg
    assert "https://example.com/cat.jpg" in flattened_msg

    vision_caps = {"id": "test-vision-model", "vision": True}
    sanitized_vision = sanitize_payload(multimodal_payload, vision_caps)
    assert isinstance(sanitized_vision["messages"][0]["content"], list)

    with patch("main.call_model_direct") as mock_direct:
        user_params = {"model": "gpt-4o"}
        mock_direct.return_value = {"choices": [{"message": {"content": "gemini-3.5-flash-lite"}}]}

        chosen = await main_mod.choose_model(
            "Look at this", user_params=user_params, image_url="https://example.com/pic.png"
        )
        assert chosen.get("vision") is True

        call_args = mock_direct.call_args[0]
        payload = call_args[2]
        system_content = payload["messages"][0]["content"]
        assert "[Vision]" in system_content
