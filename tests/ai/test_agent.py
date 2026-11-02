# tests/ai/test_agent.py
"""
Tests for the AI agent loop, tool filtering, disabled tool protection,
and argument parsing.
"""

from unittest.mock import AsyncMock, patch
import pytest

from systems.ai.agent import run_agent_loop


@pytest.mark.asyncio
async def test_agent_tool_loop_rejects_disabled_tools():
    """Verify run_agent_loop disallows tool calls for tools disabled in active_tools."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "execute_code",
                                "arguments": '{"code": "print(1)"}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    finish_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Done",
                    "tool_calls": None,
                }
            }
        ]
    }

    with patch(
        "systems.ai.agent.call_provider",
        AsyncMock(
            side_effect=[
                (mock_response, "openai/gpt-oss-20b"),
                (finish_response, "openai/gpt-oss-20b"),
            ]
        ),
    ):
        with patch("systems.ai.agent.dispatch_tool_call") as mock_dispatch:
            await run_agent_loop(
                "gpt-oss-20b",
                [{"role": "user", "content": "test"}],
                {"tooling": "web_search", "model": "openai/gpt-oss-20b"},
            )
            mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_agent_loop_handles_dict_and_null_arguments():
    """Verify run_agent_loop does not crash when tool arguments is a dict or None."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {"name": "web_search", "arguments": {"query": "test"}},
                        },
                        {
                            "id": "c2",
                            "function": {"name": "web_search", "arguments": None},
                        },
                    ],
                }
            }
        ]
    }
    finish_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Finished",
                    "tool_calls": None,
                }
            }
        ]
    }

    with patch(
        "systems.ai.agent.call_provider",
        AsyncMock(
            side_effect=[
                (mock_response, "openai/gpt-oss-20b"),
                (finish_response, "openai/gpt-oss-20b"),
            ]
        ),
    ):
        with patch(
            "systems.ai.agent.dispatch_tool_call",
            AsyncMock(return_value=("tool output", [])),
        ):
            res = await run_agent_loop(
                "gpt-oss-20b",
                [{"role": "user", "content": "test"}],
                {"tooling": "True", "model": "openai/gpt-oss-20b"},
            )
            assert res.get("raw_response") == "Finished"


@pytest.mark.asyncio
async def test_agent_tool_filtering():
    """Verify agent.py runs with only user-enabled tools."""
    user_params = {"tooling": "web_search,execute_code", "reasoning": "none"}
    base_messages = [{"role": "user", "content": "test prompt"}]

    captured_payload = None

    async def mock_call_provider(key, payload):
        nonlocal captured_payload
        captured_payload = payload
        return {"choices": [{"message": {"content": "Final answer"}}]}, "qwen/qwen3.8-27b"

    with patch("systems.ai.agent.call_provider", new=mock_call_provider):
        await run_agent_loop("qwen3.8-27b", base_messages, user_params)

    assert captured_payload is not None
    tool_names = [t["function"]["name"] for t in captured_payload.get("tools", [])]
    assert set(tool_names) == {"web_search", "execute_code"}
    assert captured_payload.get("reasoning_effort") == "none"


@pytest.mark.asyncio
async def test_agent_tooling_disabled():
    """Verify agent.py omits tools when user sets tooling to False."""
    user_params = {"tooling": "False", "reasoning": "low"}
    base_messages = [{"role": "user", "content": "test prompt"}]

    captured_payload = None

    async def mock_call_provider(key, payload):
        nonlocal captured_payload
        captured_payload = payload
        return {"choices": [{"message": {"content": "Final answer"}}]}, "qwen/qwen3.8-27b"

    with patch("systems.ai.agent.call_provider", new=mock_call_provider):
        await run_agent_loop("qwen3.8-27b", base_messages, user_params)

    assert captured_payload is not None
    assert "tools" not in captured_payload
    assert "tool_choice" not in captured_payload
    assert captured_payload.get("reasoning_effort") == "low"
