# tests/test_audit_critical_high_1_to_4.py
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.safety import OWNER_ID
from functions.audio_gen import MAX_AUDIO_BYTES, generate_audio
from functions.image_gen import MAX_IMAGE_BYTES, generate_image
from functions.web_fetch import (
    _is_safe_ip,
    _pinned_dns_var,
    _resolve_and_check_url,
    _SafePinnedResolver,
)


# ─────────────────────────────────────────────────────────────
# 1. Critical #1: /diagnose Event Loop & Concurrency Protection
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_diagnose_restricted_to_owner():
    import commands.diagnose as diagnose_module

    bot = MagicMock()
    cog = diagnose_module.DiagnoseCommand(bot)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.id = 999999999  # Not OWNER_ID
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    await cog.diagnose.callback(cog, interaction, duration=5)
    interaction.response.send_message.assert_awaited_once_with(
        "⛔ This command is restricted.", ephemeral=True
    )
    interaction.response.defer.assert_not_called()


@pytest.mark.asyncio
async def test_diagnose_prevents_concurrent_runs_and_uses_to_thread():
    import commands.diagnose as diagnose_module

    bot = MagicMock()
    bot.latency = 0.05
    bot.rate_limiter = None
    cog = diagnose_module.DiagnoseCommand(bot)

    # 1. Simulate lock already held -> rejects concurrent run
    async with cog._lock:
        int_concurrent = MagicMock(spec=discord.Interaction)
        int_concurrent.user.id = OWNER_ID
        int_concurrent.response.send_message = AsyncMock()
        await cog.diagnose.callback(cog, int_concurrent, duration=1)
        int_concurrent.response.send_message.assert_awaited_once()
        assert "already in progress" in int_concurrent.response.send_message.call_args.args[0]

    # 2. Normal owner run offloads rendering to asyncio.to_thread and respects existing sys.getprofile
    int_owner = MagicMock(spec=discord.Interaction)
    int_owner.user.id = OWNER_ID
    int_owner.response.defer = AsyncMock()
    int_owner.followup.send = AsyncMock()

    with patch.object(
        diagnose_module.asyncio,
        "to_thread",
        wraps=asyncio.to_thread,
    ) as spy_to_thread:
        await cog.diagnose.callback(cog, int_owner, duration=1)
        spy_to_thread.assert_called_once()
        assert spy_to_thread.call_args.args[0] is diagnose_module._render_diagnostics_sync
        int_owner.followup.send.assert_awaited_once()


# ─────────────────────────────────────────────────────────────
# 2. Critical #2: SSRF Protection (IPv4-Mapped IPv6 & DNS Pinning)
# ─────────────────────────────────────────────────────────────
def test_web_fetch_ipv4_mapped_and_transitional_ipv6_blocked():
    # IPv4-mapped IPv6 private/loopback/metadata
    assert _is_safe_ip("::ffff:127.0.0.1") is False
    assert _is_safe_ip("::ffff:169.254.169.254") is False
    assert _is_safe_ip("::ffff:10.0.0.1") is False
    assert _is_safe_ip("::ffff:192.168.1.1") is False
    # NAT64 transitional prefix
    assert _is_safe_ip("64:ff9b::127.0.0.1") is False
    assert _is_safe_ip("64:ff9b::169.254.169.254") is False
    # 6to4 loopback (127.0.0.1 = 7f00:0001)
    assert _is_safe_ip("2002:7f00:0001::1") is False
    # Zone-scoped link-local
    assert _is_safe_ip("fe80::1%eth0") is False
    # Public IPv4-mapped IPv6 and public IPv6 allowed
    assert _is_safe_ip("::ffff:8.8.8.8") is True
    assert _is_safe_ip("2606:4700:4700::1111") is True


@pytest.mark.asyncio
async def test_web_fetch_dns_pinning_prevents_toctou_rebinding():
    pinned = {}
    token = _pinned_dns_var.set(pinned)
    try:
        fake_addrinfo = [(2, 1, 6, "", ("93.184.216.34", 80))]
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=fake_addrinfo)) as mock_gai:
            ok, err = await _resolve_and_check_url("http://example.com/test")
            assert ok is True
            assert err == ""
            assert ("example.com", 80) in pinned
            assert mock_gai.call_count == 1

            # Resolver must return the pinned record without calling getaddrinfo a second time
            resolver = _SafePinnedResolver(pinned)
            resolved = await resolver.resolve("example.com", 80)
            assert len(resolved) == 1
            assert resolved[0]["host"] == "93.184.216.34"
            assert mock_gai.call_count == 1

        # Unpinned lookup that resolves to a private IP must raise PermissionError before connect
        evil_addrinfo = [(2, 1, 6, "", ("169.254.169.254", 80))]
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=evil_addrinfo)):
            resolver2 = _SafePinnedResolver({})
            with pytest.raises(PermissionError, match="forbidden"):
                await resolver2.resolve("rebind.attacker.com", 80)
    finally:
        _pinned_dns_var.reset(token)


# ─────────────────────────────────────────────────────────────
# 3. High #3: Database Lock Serialization & Nested Transactions
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_database_nested_transaction_savepoints_and_read_serialization(fresh_db):
    await fresh_db.ensure_user("tx_user")

    # 1. Nested transaction rollback only rolls back inner savepoint when caught,
    # and outer transaction commits cleanly
    async with fresh_db.transaction():
        await fresh_db.conn.execute(
            "UPDATE users SET roll_count = 10 WHERE user_id = ?", ("tx_user",)
        )
        with pytest.raises(ValueError):
            async with fresh_db.transaction():
                await fresh_db.conn.execute(
                    "UPDATE users SET roll_count = 999 WHERE user_id = ?", ("tx_user",)
                )
                raise ValueError("abort inner")

    user = await fresh_db.get_user_data("tx_user")
    assert user["roll_count"] == 10

    # 2. Concurrent read waits for active transaction rollback and never sees dirty state
    read_observed = []

    async def writer_that_rolls_back():
        with pytest.raises(RuntimeError):
            async with fresh_db.transaction():
                await fresh_db.conn.execute(
                    "UPDATE users SET autoroll_active = 1 WHERE user_id = ?", ("tx_user",)
                )
                await asyncio.sleep(0.05)
                raise RuntimeError("rollback outer")

    async def concurrent_reader():
        await asyncio.sleep(0.01)
        rollers = await fresh_db.get_active_rollers()
        read_observed.extend(rollers)

    await asyncio.gather(writer_that_rolls_back(), concurrent_reader())
    assert "tx_user" not in read_observed

    # 3. Leaderboard and stats queries execute safely under db._lock
    import commands.leaderboard as leaderboard_module

    bot = MagicMock()
    view = leaderboard_module.LeaderboardView(bot)
    lb_data = await view.get_leaderboard_data()
    assert any(uid == "tx_user" for uid, _ in lb_data)

    stats = await fresh_db.get_general_stats()
    assert stats["total_users"] >= 1


# ─────────────────────────────────────────────────────────────
# 4. High #4: Bounded Memory Reads on External Downloads
# ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_filter_rejects_oversized_avatar():
    import commands.filter as filter_module

    bot = MagicMock()
    cog = filter_module.FilterCommand(bot)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.display_avatar.url = "https://cdn.discordapp.com/avatars/1/2.png"
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.content_length = filter_module.MAX_AVATAR_BYTES + 1024

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(filter_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        choice = MagicMock()
        choice.value = "blur"
        await cog.filter.callback(cog, interaction, style=choice, user=None)
        interaction.followup.send.assert_awaited_once()
        assert "too large" in interaction.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_transcribe_streams_bounded_and_cleans_up_tempfile():
    import commands.transcribe as transcribe_module

    interaction = MagicMock(spec=discord.Interaction)
    interaction.followup.send = AsyncMock()

    attachment = MagicMock(spec=discord.Attachment)
    attachment.filename = "voice.mp3"
    attachment.size = 1000  # Claims 1 KB in Discord metadata
    attachment.url = "https://cdn.discordapp.com/attachments/1/2/voice.mp3"

    # Case 1: Server streams more than MAX_FILE_SIZE despite small attachment.size
    async def oversized_chunks(_chunk_size):
        yield b"x" * (transcribe_module.MAX_FILE_SIZE + 10)

    mock_resp_over = MagicMock()
    mock_resp_over.status = 200
    mock_resp_over.content_length = None
    mock_resp_over.content.iter_chunked = oversized_chunks

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp_over)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(transcribe_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        await transcribe_module.process_transcription(interaction, attachment)
        interaction.followup.send.assert_awaited_once_with(
            "❌ File size exceeds the 25 MB limit for transcription."
        )

    # Case 2: Valid audio streams to temp file, posts file stream to Groq, and deletes temp file
    interaction.followup.send.reset_mock()
    recorded_temp_paths = []

    async def valid_chunks(_chunk_size):
        yield b"fake mp3 audio content"

    mock_resp_ok = MagicMock()
    mock_resp_ok.status = 200
    mock_resp_ok.content_length = 22
    mock_resp_ok.content.iter_chunked = valid_chunks

    mock_post_resp = MagicMock()
    mock_post_resp.status = 200
    mock_post_resp.json = AsyncMock(return_value={"text": "Hello from audio"})

    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp_ok)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_post_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    orig_transcribe = transcribe_module.transcribe_audio_from_bytes

    async def spy_transcribe(source, fname):
        assert isinstance(source, str) and os.path.exists(source)
        recorded_temp_paths.append(source)
        return await orig_transcribe(source, fname)

    with (
        patch.object(transcribe_module, "get_session", AsyncMock(return_value=mock_session)),
        patch("providers.get_session", AsyncMock(return_value=mock_session)),
    ):
        with patch.object(
            transcribe_module, "transcribe_audio_from_bytes", side_effect=spy_transcribe
        ):
            await transcribe_module.process_transcription(interaction, attachment)

    assert len(recorded_temp_paths) == 1
    assert not os.path.exists(recorded_temp_paths[0]), "Temp audio file was not cleaned up!"
    interaction.followup.send.assert_awaited_once()
    assert "Hello from audio" in interaction.followup.send.call_args.args[0]


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

    with patch("functions.image_gen.get_session", AsyncMock(return_value=mock_session)):
        img_res = await generate_image("test prompt")
        assert img_res is None
        mock_resp_img.content.read.assert_awaited_once_with(MAX_IMAGE_BYTES + 1)

    with patch("functions.audio_gen.get_session", AsyncMock(return_value=mock_session)):
        aud_res = await generate_audio("test speech")
        assert aud_res is None
        mock_resp_aud.content.read.assert_awaited_once_with(MAX_AUDIO_BYTES + 1)
