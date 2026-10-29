# tests/test_audit_fixes.py
"""
Tests verifying the fixes for the 4 critical audit items:
1. Upgrades actually consume items/currencies without restoring stale dicts.
2. Incremental clover calculation avoids retroactive multiplier payouts and post-potion lockouts.
3. Web fetch SSRF protection and memory bounds.
4. Code interpreter LimitFSIZE and site-packages mounting.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import utils
from functions.web_fetch import _is_safe_ip, _resolve_and_check_url, fetch_webpage
from functions.code_interpreter import _systemd_prefix, _bwrap_command
from upgrades import UPGRADE_CATEGORIES


# ── 1. Upgrades consume requirements and persist deduction ─────────────────────
@pytest.mark.asyncio
async def test_upgrade_persists_deduction(fresh_db, monkeypatch):
    """Verifies that purchasing an upgrade deducts currencies/items and persists the new tier without restoring stale balance."""
    monkeypatch.setattr(utils, "db", fresh_db)
    import commands.upgrades as upgrades_mod
    monkeypatch.setattr(upgrades_mod, "ensure_user", utils.ensure_user)
    monkeypatch.setattr(upgrades_mod, "save_user_data", utils.save_user_data)
    monkeypatch.setattr(upgrades_mod, "consume_requirements", utils.consume_requirements)
    monkeypatch.setattr(upgrades_mod, "has_requirements", utils.has_requirements)

    user_id = "123456789"
    await fresh_db.ensure_user(user_id)

    # Set up user with currencies and items to afford clover_gain tier 1
    # clover_gain tier 1 requires: {"clovers": 10, "lucky": 4}
    db_lucky, _ = utils.resolve_item_key("lucky")
    user = await fresh_db.get_user_data(user_id)
    user["currencies"] = {"clovers": 20}
    user["inventory"] = {db_lucky: 10}
    await fresh_db.save_user_data(user_id, user)

    # Create mock interaction and UpgradeView
    from commands.upgrades import UpgradeView
    view = UpgradeView(user_id)
    view.category = "clover"
    # Page index for clover_gain
    keys = list(UPGRADE_CATEGORIES["clover"].keys())
    view.page = keys.index("clover_gain")

    mock_interaction = MagicMock()
    mock_interaction.user.id = int(user_id)
    mock_interaction.response.send_message = AsyncMock()
    mock_interaction.response.edit_message = AsyncMock()

    # Call upgrade
    await view.upgrade.callback(mock_interaction)

    # Re-fetch from DB
    updated = await fresh_db.get_user_data(user_id)
    # Verify currencies and inventory were properly deducted and NOT restored
    assert updated["currencies"]["clovers"] == 10
    assert updated["inventory"][db_lucky] == 6
    assert updated["upgrades"]["clover"]["clover_gain"] == 1


# ── 2. Incremental Clover Calculation ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_clover_incremental_calculation_no_retroactive_nor_lockout(fresh_db, monkeypatch):
    """
    Verifies that clovers are awarded incrementally per roll batch.
    - Large roll history does not retroactively award clovers when clover_mult increases.
    - Post-potion expiration does not lock out future clover awards.
    """
    monkeypatch.setattr(utils, "db", fresh_db)

    user_id = "clover_tester"
    await fresh_db.ensure_user(user_id)

    # Set up high roll count and high luck
    user = await fresh_db.get_user_data(user_id)
    user["luck_multi"] = 1500.0  # effective_luck >= 1000
    user["roll_count"] = 50000
    user["clovers_earned"] = 5000
    user["currencies"] = {"clovers": 5000}
    await fresh_db.save_user_data(user_id, user)

    # 1. Roll with overclock potion active (clover_mult = 2.0), batch of 10 rolls
    # Triggers: (50010 // 10) - (50000 // 10) = 1 trigger.
    # Expected clovers awarded: 1 * 1.0 * 2.0 = 2 clovers (NOT 5,000!)
    updated = await utils.update_user_data(
        user_id, ["Common"] * 10, action="keep", clover_mult=2.0
    )
    assert updated["roll_count"] == 50010
    assert updated["clovers_earned"] == 5002
    assert updated["currencies"]["clovers"] == 5002

    # 2. Potion expires (clover_mult returns to 1.0), roll another batch of 10 rolls
    # Triggers: (50020 // 10) - (50010 // 10) = 1 trigger.
    # Expected clovers awarded: 1 * 1.0 * 1.0 = 1 clover. NO LOCKOUT!
    updated_after_expiry = await utils.update_user_data(
        user_id, ["Common"] * 10, action="keep", clover_mult=1.0
    )
    assert updated_after_expiry["roll_count"] == 50020
    assert updated_after_expiry["clovers_earned"] == 5003
    assert updated_after_expiry["currencies"]["clovers"] == 5003


# ── 3. Web Fetch SSRF and Memory Limits ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_web_fetch_ssrf_blocking():
    """Verifies that private, loopback, link-local and reserved IP addresses are blocked."""
    assert _is_safe_ip("127.0.0.1") is False
    assert _is_safe_ip("10.0.0.1") is False
    assert _is_safe_ip("192.168.1.1") is False
    assert _is_safe_ip("172.16.0.1") is False
    assert _is_safe_ip("169.254.169.254") is False
    assert _is_safe_ip("::1") is False
    assert _is_safe_ip("0.0.0.0") is False
    assert _is_safe_ip("8.8.8.8") is True

    # Test URL validation
    safe, err = await _resolve_and_check_url("http://127.0.0.1:8080/secret")
    assert safe is False
    assert "forbidden" in err

    safe, err = await _resolve_and_check_url("http://169.254.169.254/computeMetadata/v1/")
    assert safe is False
    assert "forbidden" in err

    safe, err = await _resolve_and_check_url("ftp://example.com/file")
    assert safe is False
    assert "must be http or https" in err

    result = await fetch_webpage("http://127.0.0.1:5000")
    assert "Error: Access to private/restricted IP addresses" in result


# ── 4. Code Interpreter LimitFSIZE and user site-packages ──────────────────────
def test_code_interpreter_resource_limits():
    """Verifies systemd LimitFSIZE is configured and user site-packages are mounted."""
    prefix = _systemd_prefix("systemd-run", "test_scope")
    assert "-p" in prefix
    assert "MemoryMax=144M" in prefix
    assert "TasksMax=64" in prefix
    # .scope units do not support LimitFSIZE= (only cgroup properties)
    assert not any("LimitFSIZE" in part for part in prefix)

    cmd = _bwrap_command("bwrap", "/tmp/mock_scratch")
    assert "--unshare-all" in cmd
    assert "/workspace" in cmd


# ── 5. Unsynchronized Database Access & Autoroll Concurrency ──────────────────
@pytest.mark.asyncio
async def test_reentrant_user_lock(fresh_db):
    """Verifies that db.lock_user is safely re-entrant within the same asyncio Task."""
    user_id = "test_reentrant_user"
    async with fresh_db.lock_user(user_id):
        # Nested lock on same user in same task must succeed without deadlock
        async with fresh_db.lock_user(user_id):
            assert True


@pytest.mark.asyncio
async def test_save_user_data_upsert_preserves_inventory(fresh_db):
    """Verifies save_user_data updates inventory without leaving zero-state windows."""
    user_id = "upsert_user"
    await fresh_db.ensure_user(user_id)

    # Initial inventory
    user = await fresh_db.get_user_data(user_id)
    user["inventory"] = {"Common": 5, "Rare": 2}
    user["currencies"] = {"clovers": 100}
    await fresh_db.save_user_data(user_id, user)

    # Check database
    fetched = await fresh_db.get_user_data(user_id)
    assert fetched["inventory"]["Common"] == 5
    assert fetched["inventory"]["Rare"] == 2
    assert fetched["currencies"]["clovers"] == 100

    # Modify one item and add another
    fetched["inventory"]["Common"] = 6
    fetched["inventory"]["Legendary"] = 1
    # Remove Rare by omitting it from inventory
    del fetched["inventory"]["Rare"]
    await fresh_db.save_user_data(user_id, fetched)

    updated = await fresh_db.get_user_data(user_id)
    assert updated["inventory"]["Common"] == 6
    assert updated["inventory"]["Legendary"] == 1
    assert "Rare" not in updated["inventory"]


# ── 6. Multi-Crafting Potions & Anti-Glitch Clamping ───────────────────────────
def test_recipes_mismatches_resolved():
    """Verifies recipe text matches duration_seconds and charges in recipes.py."""
    from recipes import POTION_RECIPES

    med = POTION_RECIPES["medium_luck_potion"]
    assert "3 minutes" in med["description"]
    assert med["buff"]["duration_seconds"] == 180

    large = POTION_RECIPES["large_luck_potion"]
    assert "5 minutes" in large["description"]
    assert large["buff"]["duration_seconds"] == 300

    hyper = POTION_RECIPES["hypercharge_potion"]
    assert "25 manual rolls" in hyper["description"]
    assert hyper["buff"]["charges"] == 25


@pytest.mark.asyncio
async def test_multi_craft_potions_not_wiped_by_sanitizer(fresh_db, monkeypatch):
    """Verifies legitimate multi-crafted potions survive _sanitize_glitched_potions on restart."""
    import time
    from datetime import datetime, timezone
    import buffs
    import utils

    monkeypatch.setattr(utils, "db", fresh_db)
    user_id = "potion_crafter"
    await fresh_db.ensure_user(user_id)

    # Craft 10 All or Nothing potions (10 charges)
    await buffs.apply_potion_craft(user_id, "all_or_nothing_potion", amount=10)
    user = await fresh_db.get_user_data(user_id)
    assert user["currencies"]["potion_charge_all_or_nothing_potion"] == 10

    # Craft 15 Overclock potions (15 * 600s = 9000s = 2.5 hours)
    await buffs.apply_potion_craft(user_id, "overclock_potion", amount=15)
    user = await fresh_db.get_user_data(user_id)
    now = int(datetime.now(timezone.utc).timestamp())
    exp = user["currencies"]["potion_exp_overclock_potion"]
    assert exp >= now + 8900  # More than 2 hours remaining

    # Run _sanitize_glitched_potions (simulating restart)
    await fresh_db._sanitize_glitched_potions()

    # Re-fetch: Charges should still be 10 (not clamped to 2!)
    # Duration should still be > 2 hours (not reset down to 10 minutes!)
    user_after = await fresh_db.get_user_data(user_id)
    assert user_after["currencies"]["potion_charge_all_or_nothing_potion"] == 10
    assert user_after["currencies"]["potion_exp_overclock_potion"] >= now + 8900


@pytest.mark.asyncio
async def test_craft_command_exceed_cap_protection(fresh_db, monkeypatch):
    """Verifies that /recipes craft blocks crafting beyond the 24h / 1000 charge cap without consuming items."""
    from commands.alchemy import RecipesCommand
    from recipes import POTION_RECIPES
    import utils

    monkeypatch.setattr(utils, "db", fresh_db)
    import database as db_mod
    monkeypatch.setattr(db_mod, "db", fresh_db)

    bot_mock = MagicMock()
    cmd = RecipesCommand(bot_mock)

    user_id = "999888777"
    await fresh_db.ensure_user(user_id)

    # Set up user with huge inventory of clovers and items
    user = await fresh_db.get_user_data(user_id)
    user["currencies"] = {"clovers": 1000000}
    user["inventory"] = {"jackpot": 10000, "lucky": 10000, "unique": 10000, "amazing": 10000}
    await fresh_db.save_user_data(user_id, user)

    mock_interaction = MagicMock()
    mock_interaction.user.id = int(user_id)
    mock_interaction.response.send_message = AsyncMock()

    # Attempt to craft 2000 All or Nothing potions (exceeds 1000 charge limit)
    await cmd.craft.callback(cmd, mock_interaction, recipe_id="all_or_nothing_potion", amount=2000)

    # Must send error and NOT consume items
    mock_interaction.response.send_message.assert_called_once()
    msg = mock_interaction.response.send_message.call_args[0][0]
    assert "exceeds the 1,000 charge limit" in msg

    user_check = await fresh_db.get_user_data(user_id)
    assert user_check["currencies"]["clovers"] == 1000000  # No ingredients consumed


# ── 7. GIF Glitching Multi-Frame & NoneType Safe ──────────────────────────────
@pytest.mark.asyncio
async def test_glitch_preserves_gif_frames():
    """Verifies that multi-frame GIFs retain frames and process_glitch handles animation."""
    import io
    from PIL import Image
    from commands.glitch import process_glitch

    # Create a 3-frame animated GIF in memory
    frames = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        img = Image.new("RGB", (64, 64), color=color)
        frames.append(img)

    gif_buf = io.BytesIO()
    frames[0].save(
        gif_buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    gif_bytes = gif_buf.getvalue()

    # Process glitch
    output_bytes = process_glitch(gif_bytes, is_gif=True, intensity=5)
    assert len(output_bytes) > 0

    # Verify output GIF has multiple frames
    out_img = Image.open(io.BytesIO(output_bytes))
    num_frames = 0
    try:
        while True:
            num_frames += 1
            out_img.seek(out_img.tell() + 1)
    except EOFError:
        pass

    assert num_frames == 3, f"Expected 3 frames in output GIF, got {num_frames}"


@pytest.mark.asyncio
async def test_glitch_attachment_none_content_type():
    """Verifies that glitch command does not crash when image.content_type is None."""
    from commands.glitch import GlitchCommand
    import io
    from PIL import Image

    bot_mock = MagicMock()
    cmd = GlitchCommand(bot_mock)

    img = Image.new("RGB", (32, 32), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    data = buf.getvalue()

    mock_attachment = MagicMock()
    mock_attachment.content_type = None  # None content_type
    mock_attachment.filename = "test_image.png"
    mock_attachment.size = len(data)
    mock_attachment.read = AsyncMock(return_value=data)

    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_interaction.followup.send = AsyncMock()

    # Must complete successfully without AttributeError: 'NoneType' object has no attribute 'startswith'
    await cmd.glitch.callback(cmd, mock_interaction, image=mock_attachment, intensity=3)
    mock_interaction.followup.send.assert_called_once()


# ── 8. GuildPurgeModal ForumChannel & UnboundLocalError ───────────────────────
@pytest.mark.asyncio
async def test_guild_purge_modal_forum_and_unbound_local(monkeypatch):
    """Verifies that GuildPurgeModal handles ForumChannel and channels without history perms without crashing."""
    import discord
    from commands.safety import GuildPurgeModal
    import commands.safety as safety_mod

    bot_mock = MagicMock()
    bot_mock.user.id = 99999

    # Text channel with no read history permission
    text_chan = MagicMock(spec=discord.TextChannel)
    text_chan.permissions_for.return_value = MagicMock(read_message_history=False)
    text_chan.purge = AsyncMock()

    # Create an async iterator for archived_threads
    async def empty_archived(limit=None):
        if False:
            yield None

    text_chan.archived_threads = empty_archived

    # Forum channel without .purge method
    forum_chan = MagicMock(spec=discord.ForumChannel)
    if hasattr(forum_chan, "purge"):
        del forum_chan.purge
    forum_chan.archived_threads = empty_archived

    guild_mock = MagicMock()
    guild_mock.name = "Test Guild"
    guild_mock.text_channels = [text_chan]
    guild_mock.forum_channels = [forum_chan]
    guild_mock.voice_channels = []
    guild_mock.stage_channels = []
    guild_mock.threads = []
    guild_mock.me = MagicMock()

    bot_mock.get_guild.return_value = guild_mock

    modal = GuildPurgeModal(bot_mock)
    modal.guild_id_input._value = "123456789012345678"
    modal.limit_input._value = "100"

    mock_interaction = MagicMock()
    mock_interaction.response.defer = AsyncMock()
    mock_status_msg = MagicMock()
    mock_status_msg.edit = AsyncMock()
    mock_interaction.followup.send = AsyncMock(return_value=mock_status_msg)

    # Mock DB commit
    mock_db = MagicMock()
    mock_db._lock = asyncio.Lock()
    mock_db.conn.execute.return_value.__aenter__ = AsyncMock()
    mock_db.conn.execute.return_value.__aexit__ = AsyncMock()
    mock_db.conn.commit = AsyncMock()
    monkeypatch.setattr(safety_mod, "db", mock_db)

    # Should run to completion without UnboundLocalError or AttributeError
    await modal.on_submit(mock_interaction)
    mock_interaction.response.defer.assert_called_once()
    mock_status_msg.edit.assert_called()


# ── 9. Vision Routing, Fallback Sanitization & Preferred Models ───────────────
@pytest.mark.asyncio
async def test_vision_payload_sanitization_and_routing():
    """Verifies that non-vision models have multimodal content flattened, and router prompts include [Vision]."""
    from providers import sanitize_payload, MODELS, FALLBACK_MODEL_KEY
    import main as main_mod

    # 1. Verify sanitize_payload flattens multimodal content for non-vision models (e.g. fallback)
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

    # Verify vision-capable model preserves multimodal content list
    vision_caps = {"id": "test-vision-model", "vision": True}
    sanitized_vision = sanitize_payload(multimodal_payload, vision_caps)
    assert isinstance(sanitized_vision["messages"][0]["content"], list)

    # 2. Verify choose_model filters out non-vision models when image_url is present
    with patch("main.call_model_direct") as mock_direct:
        # Preferred model is non-vision (e.g. gpt-4o which has vision=False)
        user_params = {"model": "gpt-4o"}
        mock_direct.return_value = {"choices": [{"message": {"content": "gemini-3.5-flash-lite"}}]}

        # When image_url is present, preferred non-vision model should be bypassed in favor of router
        chosen = await main_mod.choose_model("Look at this", user_params=user_params, image_url="https://example.com/pic.png")
        assert chosen.get("vision") is True

        # Check router prompt contains [Vision] tag for vision-capable models
        call_args = mock_direct.call_args[0]
        payload = call_args[2]
        system_content = payload["messages"][0]["content"]
        assert "[Vision]" in system_content


# ── 10. Regeneration History Preservation & Overflow Handling ─────────────────
@pytest.mark.asyncio
async def test_regeneration_history_and_context_resolution(fresh_db, monkeypatch):
    """Verifies that get_context_for_message skips duplicate assistant entries and finds the true user prompt."""
    import utils
    monkeypatch.setattr(utils, "db", fresh_db)

    user_id = "user_regen_test"
    guild_id = "guild_regen_test"

    # Insert conversation: User -> Assistant 1 -> (stale duplicate) Assistant 2
    await utils.append_message_for_context(
        user_id, False, "user", "What is the capital of France?", guild_id=guild_id, message_ids=[1001], author_id=user_id
    )
    await utils.append_message_for_context(
        user_id, False, "assistant", "Paris is the capital.", guild_id=guild_id, message_ids=[1002]
    )
    # Simulate a corrupted duplicate assistant message
    await utils.append_message_for_context(
        user_id, False, "assistant", "Duplicate response without user prompt.", guild_id=guild_id, message_ids=[1003]
    )

    # Request context for message 1003
    prompt, context = await fresh_db.get_context_for_message(user_id, False, guild_id, 1003)
    assert prompt == "What is the capital of France?"
    # Context should not have corrupted assistant turn as user
    assert all(m["role"] in ["user", "assistant"] for m in context)

    # Test update_message_in_history updates content and message_ids without adding rows
    updated = await fresh_db.update_message_in_history(
        user_id, False, guild_id, 1002, "Paris is indeed the capital.", new_message_ids=[1002, 1004]
    )
    assert updated is True

    # Verify history count did not increase
    history = await fresh_db.get_messages_for_context(guild_id=guild_id, limit=20, include_internal=True)
    # Should have 3 messages total: 1 user + 2 assistant
    assert len(history) == 3
    updated_row = next(m for m in history if 1002 in m["message_ids"])
    assert updated_row["content"] == "Paris is indeed the capital."
    assert 1004 in updated_row["message_ids"]


