import asyncio
import json
import os
import io
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

import utils
from functions.code_interpreter import _systemd_prefix, _set_sandbox_rlimits
from functions.forum_post import create_forum_post, _forum_post_timestamps
from agent import run_agent_loop
from providers import sanitize_payload
import commands.ocr as ocr_module
import commands.txt2img as txt2img_module
import commands.tts as tts_module
import functions.web_fetch as web_fetch_module


# ─────────────────────────────────────────────────────────────
# Bug 1: Sandbox LimitFSIZE & RLIMIT_FSIZE
# ─────────────────────────────────────────────────────────────
def test_sandbox_systemd_scope_no_limitfsize():
    """Verify that _systemd_prefix does not include LimitFSIZE which breaks .scope units."""
    prefix = _systemd_prefix("systemd-run", "test_scope")
    assert "-p" in prefix
    assert "LimitFSIZE=16M" not in prefix
    assert "LimitFSIZE" not in " ".join(prefix)


def test_sandbox_rlimits_function():
    """Verify _set_sandbox_rlimits behaves safely across platforms."""
    _set_sandbox_rlimits()


# ─────────────────────────────────────────────────────────────
# Bug 2: Tool Loop Authorization & Forum Post Protection
# ─────────────────────────────────────────────────────────────
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
        "agent.call_provider",
        AsyncMock(
            side_effect=[
                (mock_response, "openai/gpt-oss-20b"),
                (finish_response, "openai/gpt-oss-20b"),
            ]
        ),
    ):
        with patch("agent.dispatch_tool_call") as mock_dispatch:
            res = await run_agent_loop(
                "gpt-oss-20b",
                [{"role": "user", "content": "test"}],
                {"tooling": "web_search", "model": "openai/gpt-oss-20b"},
            )
            mock_dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_forum_post_safeguard_and_rate_limit():
    """Verify forum_post enforces 1/hr rate limit, safeguard check, and user attribution."""
    _forum_post_timestamps.clear()
    user_id = "user_999"

    mock_bot = MagicMock()

    # 1. Unsafe content blocked by safeguard
    with patch(
        "functions.forum_post.check_safeguard",
        AsyncMock(return_value={"verdict": "unsafe_output", "reasoning": "malicious"}),
    ):
        res, thread = await create_forum_post(mock_bot, "bad title", "bad body", user_id=user_id)
        assert "safeguard policy" in res.lower()

    # 2. Safe content succeeds and adds attribution
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

    with patch("functions.forum_post.check_safeguard", AsyncMock(return_value={"verdict": "safe"})):
        res, thread = await create_forum_post(mock_bot, "Good title", "Good body", user_id=user_id)
        assert "Successfully created forum post" in res
        call_kwargs = mock_channel.create_thread.call_args.kwargs
        assert f"Requested by <@{user_id}>" in call_kwargs["content"]

        # 3. Second post by same user triggers rate limit
        res2, thread2 = await create_forum_post(
            mock_bot, "Second title", "Second body", user_id=user_id
        )
        assert "Rate limit exceeded" in res2


# ─────────────────────────────────────────────────────────────
# Bug 3: Cross-Channel History Isolation
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_conversation_history_channel_isolation(fresh_db):
    """Verify server messages in channel A do not leak into channel B."""
    guild_id = "guild_1"
    channel_a = "chan_A"
    channel_b = "chan_B"

    await fresh_db.add_conversation_message(
        None, guild_id, "user", "Admin secret token 12345", channel_id=channel_a, author_id=111
    )
    await fresh_db.add_conversation_message(
        None,
        guild_id,
        "assistant",
        "Acknowledged secret token",
        channel_id=channel_a,
        author_id=111,
    )

    chan_b_msgs = await fresh_db.get_messages_for_context(
        None, guild_id=guild_id, channel_id=channel_b
    )
    assert len(chan_b_msgs) == 0

    chan_a_msgs = await fresh_db.get_messages_for_context(
        None, guild_id=guild_id, channel_id=channel_a
    )
    assert len(chan_a_msgs) == 2
    assert "12345" in chan_a_msgs[0]["content"]


# ─────────────────────────────────────────────────────────────
# Bug 4: Atomic Potion Charge Deduction
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_buffs_charge_atomic_deduction():
    """Verify evaluate_active_buffs only sets is_active if currency_remove returns True."""
    import buffs

    user_id = 5555

    with patch("buffs.currency_count", AsyncMock(return_value=1)):
        with patch("buffs.currency_remove", AsyncMock(return_value=False)):
            res = await buffs.evaluate_active_buffs(user_id, context="manual")
            assert res.get("luck_mult", 1.0) == 1.0


# ─────────────────────────────────────────────────────────────
# Bug 5: Clover Multiplier Calculation & Potion Overwrite
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_clover_base_multiplier_calculation(fresh_db):
    """Verify clover multiplier does not double-count base 1.0."""
    await fresh_db.ensure_user(1234)
    with patch("buffs.evaluate_active_buffs", AsyncMock(return_value={"clover_mult": 1.0})):
        user = await fresh_db.get_user_data(1234)
        user["luck_multi"] = 1000.0
        user["roll_count"] = 99
        await fresh_db.save_user_data(1234, user)

        updated = await utils.update_user_data(1234, "Common", action="keep")
        # Rolled from 99 to 100 -> exactly 1 clover with 1.0 multi (not 2 clovers)
        assert updated["currencies"]["clovers"] == 1


# ─────────────────────────────────────────────────────────────
# Bug 7: Agent Non-String Args & GPT-OSS reasoning_effort
# ─────────────────────────────────────────────────────────────
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
        "agent.call_provider",
        AsyncMock(
            side_effect=[
                (mock_response, "openai/gpt-oss-20b"),
                (finish_response, "openai/gpt-oss-20b"),
            ]
        ),
    ):
        with patch("agent.dispatch_tool_call", AsyncMock(return_value=("tool output", []))):
            res = await run_agent_loop(
                "gpt-oss-20b",
                [{"role": "user", "content": "test"}],
                {"tooling": "True", "model": "openai/gpt-oss-20b"},
            )
            assert res.get("raw_response") == "Finished"


# ─────────────────────────────────────────────────────────────
# Bug 8: Delete Active Persona Restores Default Persona Prompts
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_delete_active_persona_restores_default_params(fresh_db):
    """Verify deleting active persona restores Default persona's prompts in user_params."""
    user_id = "test_user_789"
    await fresh_db.ensure_user(int("789"))
    await fresh_db.add_persona(user_id, "Default", "Default user", "Default AI")

    # Add custom persona and equip it
    await fresh_db.add_persona(user_id, "Pirate", "Ahoy matey", "Talk like a pirate")
    await fresh_db.equip_persona(user_id, "Pirate")

    params = await fresh_db.get_user_params(user_id)
    assert params["active_persona"] == "Pirate"
    assert params["ai_persona"] == "Talk like a pirate"

    # Delete active persona
    deleted = await fresh_db.delete_persona(user_id, "Pirate")
    assert deleted is True

    # Check that Default was restored along with Default prompts
    new_params = await fresh_db.get_user_params(user_id)
    assert new_params["active_persona"] == "Default"
    assert new_params["ai_persona"] == "Default AI"
    assert new_params["user_persona"] == "Default user"


# ─────────────────────────────────────────────────────────────
# Bug 9: OCR limits & txt2img/tts safeguard
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ocr_size_limit_and_rate_limit():
    """Verify /ocr checks file size limit and rate limiter."""
    mock_bot = MagicMock()
    mock_bot.rate_limiter = MagicMock()
    mock_bot.rate_limiter.check.return_value = (True, 0.0, None)
    ocr_cog = ocr_module.OCRCommand(mock_bot)

    mock_interaction = MagicMock()
    mock_interaction.user.id = 12345
    mock_interaction.response.send_message = AsyncMock()

    mock_file = MagicMock()
    mock_file.size = 10 * 1024 * 1024  # 10 MB > 8 MB cap
    mock_file.content_type = "image/png"

    await ocr_cog.ocr_slash.callback(ocr_cog, mock_interaction, mock_file)
    mock_interaction.response.send_message.assert_called_with(
        "❌ Image is too large (maximum allowed size is 8 MB).", ephemeral=True
    )


@pytest.mark.asyncio
async def test_txt2img_safeguard_check():
    """Verify /txt2img rejects prompts flagged by check_safeguard."""
    mock_bot = MagicMock()
    mock_bot.rate_limiter = MagicMock()
    mock_bot.rate_limiter.check.return_value = (True, 0.0, None)
    mock_bot.check_safeguard = AsyncMock(
        return_value={"verdict": "unsafe_input", "reasoning": "NSFW", "violated_policy": "Explicit"}
    )
    txt2img_cog = txt2img_module.Txt2ImgCommand(mock_bot)

    mock_interaction = MagicMock()
    mock_interaction.user.id = 12345
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    await txt2img_cog.txt2img.callback(txt2img_cog, mock_interaction, prompt="bad prompt")
    call_text = mock_interaction.followup.send.call_args[0][0]
    assert "Safeguard Block" in call_text


# ─────────────────────────────────────────────────────────────
# Bug 10: Web Fetch DNS Rebinding & Async Extraction
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_web_fetch_dns_rebinding_protection():
    """Verify fetch_webpage aborts if socket peer IP is private/loopback."""
    mock_transport = MagicMock()
    mock_transport.get_extra_info.return_value = ("127.0.0.1", 80)
    mock_connection = MagicMock()
    mock_connection.transport = mock_transport

    mock_resp = AsyncMock()
    mock_resp.connection = mock_connection
    mock_resp.status = 200

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("functions.web_fetch._resolve_and_check_url", AsyncMock(return_value=(True, None))):
        with patch("aiohttp.ClientSession", return_value=mock_session):
            res = await web_fetch_module.fetch_webpage("http://evil-rebind.com")
            assert "Access to private/restricted IP addresses" in res


# ─────────────────────────────────────────────────────────────
# Item 15: Luck Override is not None Checks
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_luck_override_is_not_none_check(fresh_db):
    """Verify luck_override=0 is respected and not treated as falsy."""
    await fresh_db.ensure_user(1234)
    user = await fresh_db.get_user_data(1234)
    user["luck_override"] = 0.0
    await fresh_db.save_user_data(1234, user)

    res = await utils.roll_rarities(1234, 1)
    assert len(res) == 1
