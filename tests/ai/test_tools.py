# tests/ai/test_tools.py
"""
Tests for AI agent tools: schema integrity, code interpreter sandbox resource limits,
forum post safeguard & rate limits, media generation size bounds, and dispatcher safeguards.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import discord
import pytest

from systems.ai.functions.audio_gen import MAX_AUDIO_BYTES, generate_audio
from systems.ai.functions.code_interpreter import (
    _bwrap_command,
    _set_sandbox_rlimits,
    _systemd_prefix,
)
from systems.ai.functions.dispatcher import dispatch_tool_call
from systems.ai.functions.forum_post import _forum_post_timestamps, create_forum_post
from systems.ai.functions.image_gen import MAX_IMAGE_BYTES, generate_image
from systems.ai.functions.tools_schema import AGENT_TOOLS


def test_agent_tools_schema_valid():
    assert isinstance(AGENT_TOOLS, list) and AGENT_TOOLS
    seen_names = set()
    for tool in AGENT_TOOLS:
        assert tool.get("type") == "function"
        fn = tool["function"]
        assert fn.get("name"), "Tool missing function.name"
        assert fn["name"] not in seen_names, f"Duplicate tool name: {fn['name']}"
        seen_names.add(fn["name"])
        assert fn.get("description"), f"Tool '{fn['name']}' missing description"
        params = fn.get("parameters", {})
        assert params.get("type") == "object", (
            f"Tool '{fn['name']}' parameters.type must be 'object'"
        )
        assert "properties" in params


def test_sandbox_systemd_scope_no_limitfsize():
    """Verify that _systemd_prefix does not include LimitFSIZE which breaks .scope units."""
    prefix = _systemd_prefix("systemd-run", "test_scope")
    assert "-p" in prefix
    assert "LimitFSIZE=16M" not in prefix
    assert "LimitFSIZE" not in " ".join(prefix)


def test_sandbox_rlimits_function():
    """Verify _set_sandbox_rlimits behaves safely across platforms."""
    _set_sandbox_rlimits()


def test_code_interpreter_resource_limits():
    """Verifies systemd cgroup properties and bwrap isolation flags."""
    prefix = _systemd_prefix("systemd-run", "test_scope")
    assert "-p" in prefix
    assert "MemoryMax=144M" in prefix
    assert "TasksMax=64" in prefix
    assert not any("LimitFSIZE" in part for part in prefix)

    cmd = _bwrap_command("bwrap", "/tmp/mock_scratch")
    assert "--unshare-all" in cmd
    assert "/workspace" in cmd


@pytest.mark.asyncio
async def test_dispatcher_media_safeguard_blocks_unsafe_image_and_audio():
    context = {"files": []}

    with patch(
        "systems.ai.functions.dispatcher.check_safeguard",
        AsyncMock(
            return_value={
                "verdict": "unsafe_input",
                "reasoning": "Explicit prompt",
                "violated_policy": "NSFW",
            }
        ),
    ):
        with patch("systems.ai.functions.dispatcher.generate_image", AsyncMock()) as mock_img:
            out_img, file_img = await dispatch_tool_call(
                "generate_media",
                {"media_type": "image", "prompt": "unsafe image prompt"},
                context,
            )
            assert "blocked by safeguard policy" in out_img.lower()
            assert file_img is None
            mock_img.assert_not_called()

        with patch("systems.ai.functions.dispatcher.generate_audio", AsyncMock()) as mock_aud:
            out_aud, file_aud = await dispatch_tool_call(
                "generate_media",
                {"media_type": "audio", "input": "unsafe audio text"},
                context,
            )
            assert "blocked by safeguard policy" in out_aud.lower()
            assert file_aud is None
            mock_aud.assert_not_called()


@pytest.mark.asyncio
async def test_forum_post_safeguard_and_rate_limit():
    """Verify forum_post enforces 1/hr rate limit, safeguard check, and user attribution."""
    _forum_post_timestamps.clear()
    user_id = "user_999"

    mock_bot = MagicMock()

    with patch(
        "systems.ai.functions.forum_post.check_safeguard",
        AsyncMock(return_value={"verdict": "unsafe_output", "reasoning": "malicious"}),
    ):
        res, thread = await create_forum_post(mock_bot, "bad title", "bad body", user_id=user_id)
        assert "safeguard policy" in res.lower()

    mock_thread = MagicMock()
    mock_thread.id = 12345
    mock_thread.jump_url = "https://discord.com/channels/1/2/12345"
    mock_thread_with_msg = MagicMock()
    mock_thread_with_msg.thread = mock_thread
    mock_channel = MagicMock(spec=discord.ForumChannel)
    mock_channel.name = "urch-bot"
    mock_channel.available_tags = []
    mock_channel.create_thread = AsyncMock(return_value=mock_thread_with_msg)
    mock_bot.get_channel = MagicMock(return_value=mock_channel)

    with patch(
        "systems.ai.functions.forum_post.check_safeguard",
        AsyncMock(return_value={"verdict": "safe"}),
    ):
        res, thread = await create_forum_post(mock_bot, "Good title", "Good body", user_id=user_id)
        assert "Successfully created forum post" in res
        call_kwargs = mock_channel.create_thread.call_args.kwargs
        assert f"Requested by <@{user_id}>" in call_kwargs["content"]

        res2, thread2 = await create_forum_post(
            mock_bot, "Second title", "Second body", user_id=user_id
        )
        assert "Rate limit exceeded" in res2


@pytest.mark.asyncio
async def test_image_gen_and_audio_gen_reject_oversized_responses():
    mock_resp_img = MagicMock()
    mock_resp_img.status = 200
    mock_resp_img.content_length = None
    mock_resp_img.content.read = AsyncMock(return_value=b"x" * (MAX_IMAGE_BYTES + 1))

    mock_resp_aud = MagicMock()
    mock_resp_aud.status = 200
    mock_resp_aud.content_length = None
    mock_resp_aud.content.read = AsyncMock(return_value=b"x" * (MAX_AUDIO_BYTES + 1))

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp_img)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp_aud)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "systems.ai.functions.image_gen.get_session",
        AsyncMock(return_value=mock_session),
    ):
        img_res = await generate_image("test prompt")
        assert img_res is None
        mock_resp_img.content.read.assert_awaited_once_with(MAX_IMAGE_BYTES + 1)

    with patch(
        "systems.ai.functions.audio_gen.get_session",
        AsyncMock(return_value=mock_session),
    ):
        aud_res = await generate_audio("test speech")
        assert aud_res is None
        mock_resp_aud.content.read.assert_awaited_once_with(MAX_AUDIO_BYTES + 1)
