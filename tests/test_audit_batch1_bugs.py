# tests/test_audit_batch1_bugs.py
import math
import random
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

import utils
from commands.setluck import SetLuckCommand
from commands.pixel import PixelCommand, _generate_pixel_image_sync
from functions.dispatcher import dispatch_tool_call
from upgrades import get_upgrade_effect
from upgrades.luck_upgrades import LUCK_UPGRADES
from raritylist import RARITIES


# ─────────────────────────────────────────────────────────────
# 1. Bug #3: commands/setluck.py
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_setluck_rejects_nan_inf_and_invalid_negatives(fresh_db):
    bot = MagicMock()
    cmd = SetLuckCommand(bot)

    for bad_val in [float("nan"), float("inf"), float("-inf"), -500.0, -2.0, -0.5]:
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user.id = 111222333
        interaction.response.send_message = AsyncMock()

        await cmd.setluck.callback(cmd, interaction, value=bad_val)
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args
        assert "❌" in args[0]
        assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_setluck_remove_override_executes_sql_null_update(fresh_db):
    bot = MagicMock()
    cmd = SetLuckCommand(bot)
    user_id = "111222333"

    await fresh_db.ensure_user(user_id)
    user = await fresh_db.get_user_data(user_id)
    user["max_luck"] = 100.0
    user["luck_override"] = 50.0
    await fresh_db.save_user_data(user_id, user)

    # Verify override is set in DB
    check = await fresh_db.get_user_data(user_id)
    assert check["luck_override"] == 50.0

    # Call /setluck -1 to remove override
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = int(user_id)
    interaction.response.send_message = AsyncMock()

    await cmd.setluck.callback(cmd, interaction, value=-1.0)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "removed" in embed.description.lower()

    # Verify DB now has luck_override = None
    after = await fresh_db.get_user_data(user_id)
    assert after["luck_override"] is None

    # Calling /setluck -1 again when no override is active should report no override active
    interaction2 = MagicMock(spec=discord.Interaction)
    interaction2.user.id = int(user_id)
    interaction2.response.send_message = AsyncMock()
    await cmd.setluck.callback(cmd, interaction2, value=-1.0)
    embed2 = interaction2.response.send_message.call_args.kwargs["embed"]
    assert "No luck override active" in embed2.description


# ─────────────────────────────────────────────────────────────
# 2. Bug #5: main.py & database.py
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_context_for_message_with_author_id_no_row_get_crash(fresh_db):
    """Ensure get_context_for_message does not crash with AttributeError on aiosqlite.Row."""
    guild_id = "g_100"
    channel_id = "c_200"
    orig_author = "user_orig_111"

    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="user",
        content="Hello from original author",
        message_ids=[5001],
        author_id=orig_author,
        channel_id=channel_id,
    )
    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="assistant",
        content="Bot reply to original author",
        message_ids=[5002],
        author_id=orig_author,
        channel_id=channel_id,
    )

    prompt, context = await fresh_db.get_context_for_message(
        "admin_reactor_999", False, guild_id, 5002, channel_id=channel_id
    )
    assert prompt == "Hello from original author"
    assert context == []

    resolved_author = await fresh_db.get_original_author_for_message(
        "admin_reactor_999", False, guild_id, 5002, channel_id=channel_id
    )
    assert resolved_author == orig_author


@pytest.mark.asyncio
async def test_on_raw_reaction_add_uses_original_author_id(fresh_db, monkeypatch):
    """Verify that when an admin reacts with ♻️, the original author's ID is passed to generate_response and history."""
    import main as main_mod

    guild_id = "888888"
    channel_id = "777777"
    orig_author_id = 111111
    admin_reactor_id = 999999
    bot_user_id = 555555

    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="user",
        content="Original user question",
        message_ids=[2001],
        author_id=str(orig_author_id),
        channel_id=channel_id,
    )
    await fresh_db.add_conversation_message(
        user_id=None,
        guild_id=guild_id,
        role="assistant",
        content="Initial bot answer",
        message_ids=[2002],
        author_id=str(orig_author_id),
        channel_id=channel_id,
    )

    mock_bot_user = MagicMock()
    mock_bot_user.id = bot_user_id
    monkeypatch.setattr(main_mod.bot, "_connection", MagicMock(user=mock_bot_user))

    mock_orig_user = MagicMock()
    mock_orig_user.id = orig_author_id
    mock_orig_user.name = "OriginalUser"

    mock_channel = MagicMock()
    mock_channel.id = int(channel_id)
    mock_message = MagicMock()
    mock_message.id = 2002
    mock_message.author.id = bot_user_id
    mock_message.channel = mock_channel
    mock_message.guild = MagicMock(id=int(guild_id))
    mock_message.remove_reaction = AsyncMock()
    mock_message.edit = AsyncMock()
    mock_channel.fetch_message = AsyncMock(return_value=mock_message)

    monkeypatch.setattr(main_mod.bot, "get_channel", MagicMock(return_value=mock_channel))
    monkeypatch.setattr(
        main_mod.bot,
        "get_user",
        MagicMock(side_effect=lambda uid: mock_orig_user if uid == orig_author_id else None),
    )

    mock_generate = AsyncMock(
        return_value={
            "raw_response": "Regenerated answer",
            "display_response": "Regenerated answer",
        }
    )
    monkeypatch.setattr(main_mod, "generate_response", mock_generate)
    monkeypatch.setattr(main_mod, "check_safeguard", AsyncMock(return_value={"verdict": "safe"}))

    payload = MagicMock()
    payload.user_id = admin_reactor_id
    payload.channel_id = int(channel_id)
    payload.guild_id = int(guild_id)
    payload.message_id = 2002
    payload.emoji = "♻️"
    payload.member = MagicMock()
    payload.member.guild_permissions.administrator = True

    await main_mod.on_raw_reaction_add(payload)

    mock_generate.assert_awaited_once()
    call_args = mock_generate.call_args
    # 3rd positional arg is user_id_str; keyword 'user' is user_obj
    assert call_args.args[2] == str(orig_author_id)
    assert call_args.kwargs["user"].id == orig_author_id


# ─────────────────────────────────────────────────────────────
# 3. Bug #7: functions/dispatcher.py
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dispatcher_media_safeguard_blocks_unsafe_image_and_audio():
    context = {"files": []}

    with patch(
        "functions.dispatcher.check_safeguard",
        AsyncMock(
            return_value={
                "verdict": "unsafe_input",
                "reasoning": "Explicit prompt",
                "violated_policy": "NSFW",
            }
        ),
    ):
        with patch("functions.dispatcher.generate_image", AsyncMock()) as mock_img:
            out_img, file_img = await dispatch_tool_call(
                "generate_media",
                {"media_type": "image", "prompt": "unsafe image prompt"},
                context,
            )
            assert "blocked by safeguard policy" in out_img.lower()
            assert file_img is None
            mock_img.assert_not_called()

        with patch("functions.dispatcher.generate_audio", AsyncMock()) as mock_aud:
            out_aud, file_aud = await dispatch_tool_call(
                "generate_media",
                {"media_type": "audio", "input": "unsafe audio text"},
                context,
            )
            assert "blocked by safeguard policy" in out_aud.lower()
            assert file_aud is None
            mock_aud.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 4. Bug #9: commands/pixel.py
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pixel_isolates_rng_and_uses_to_thread():
    # Seed global random to a known state and record expected sequence
    random.seed(42)
    expected_first = random.random()

    # Re-seed global random to 42, run _generate_pixel_image_sync with a different seed,
    # and verify global random state was NOT touched!
    random.seed(42)
    _generate_pixel_image_sync(seed=999999, size=16, palette="random", pattern="random")
    actual_first = random.random()
    assert actual_first == expected_first, "Global RNG state was poisoned by pixel generation!"

    # Verify PixelCommand.pixel offloads generation to asyncio.to_thread
    bot = MagicMock()
    cmd = PixelCommand(bot)
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch(
        "commands.pixel.asyncio.to_thread", wraps=utils.db and __import__("asyncio").to_thread
    ) as spy_thread:
        await cmd.pixel.callback(
            cmd, interaction, seed=12345, size=16, palette="random", pattern="noise"
        )
        spy_thread.assert_called_once()
        interaction.followup.send.assert_awaited_once()


# ─────────────────────────────────────────────────────────────
# 5. Bug #10: upgrades/__init__.py & upgrades/luck_upgrades.py
# ─────────────────────────────────────────────────────────────
def test_exp_luck_only_applies_exponential_bonus():
    user_obj = {
        "highscore": RARITIES[10][0],  # idx = 10
        "upgrades": {
            "luck": {"exp_luck": 5},
            "roll": {},
            "clover": {},
        },
    }

    effects = get_upgrade_effect("user_1", user_obj=user_obj, checklist_exp_bonus=1.0)
    # Must NOT add any additive luck_bonus
    assert effects["luck_bonus"] == 0.0

    # Must apply expected exponential bonus: log(10 + 2) ** (0.2 * 5) = log(12) ** 1.0
    expected_exp = math.log(12) ** 1.0
    assert math.isclose(effects["exp_bonus"], expected_exp, rel_tol=1e-9)
    assert LUCK_UPGRADES["exp_luck"]["effect"](5, user_obj) == {}
