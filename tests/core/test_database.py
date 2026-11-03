# tests/core/test_database.py
"""
Database lifecycle, transaction/savepoint semantics, per-user re-entrant locks,
conversation history isolation/pruning, user params, and personas.
"""

import asyncio
from unittest.mock import MagicMock
import pytest

from systems.game import utils


@pytest.mark.asyncio
async def test_ensure_user_and_get(fresh_db):
    created = await fresh_db.ensure_user("u1")
    assert created is True
    created_again = await fresh_db.ensure_user("u1")
    assert created_again is False

    data = await fresh_db.get_user_data("u1")
    assert data is not None
    assert data["roll_count"] == 0
    assert data["luck_multi"] == 1.0
    assert data["pit_luck"] == 0.0


@pytest.mark.asyncio
async def test_pit_luck_persistence_and_roundtrip(fresh_db):
    await fresh_db.ensure_user("u_pit")
    user = await fresh_db.get_user_data("u_pit")
    assert user["pit_luck"] == 0.0

    user["pit_luck"] = 42500.75
    await fresh_db.save_user_data("u_pit", user)

    reloaded = await fresh_db.get_user_data("u_pit")
    assert reloaded["pit_luck"] == 42500.75


@pytest.mark.asyncio
async def test_get_unknown_user_returns_none(fresh_db):
    assert await fresh_db.get_user_data("nobody") is None


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_exception(fresh_db):
    await fresh_db.ensure_user("u2")

    with pytest.raises(RuntimeError):
        async with fresh_db.transaction():
            await fresh_db.conn.execute(
                "UPDATE users SET roll_count = 999 WHERE user_id = ?", ("u2",)
            )
            raise RuntimeError("boom")

    data = await fresh_db.get_user_data("u2")
    assert data["roll_count"] == 0, "Transaction did not roll back"


@pytest.mark.asyncio
async def test_transaction_commits_on_success(fresh_db):
    await fresh_db.ensure_user("u3")
    async with fresh_db.transaction():
        await fresh_db.conn.execute("UPDATE users SET roll_count = 42 WHERE user_id = ?", ("u3",))
    data = await fresh_db.get_user_data("u3")
    assert data["roll_count"] == 42


@pytest.mark.asyncio
async def test_database_nested_transaction_savepoints_and_read_serialization(fresh_db):
    await fresh_db.ensure_user("tx_user")

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

    import systems.bot.commands.leaderboard as leaderboard_module

    bot = MagicMock()
    view = leaderboard_module.LeaderboardView(bot)
    lb_data = await view.get_leaderboard_data()
    assert any(uid == "tx_user" for uid, _ in lb_data)

    stats = await fresh_db.get_general_stats()
    assert stats["total_users"] >= 1


@pytest.mark.asyncio
async def test_user_lock_serializes_writes(fresh_db):
    await fresh_db.ensure_user("u4")
    events = []

    async def worker(n):
        async with fresh_db.lock_user("u4"):
            events.append(f"start-{n}")
            await asyncio.sleep(0.05)
            events.append(f"end-{n}")

    await asyncio.gather(worker(1), worker(2))
    assert events in (
        ["start-1", "end-1", "start-2", "end-2"],
        ["start-2", "end-2", "start-1", "end-1"],
    ), f"Locks leaked: {events}"


@pytest.mark.asyncio
async def test_reentrant_user_lock(fresh_db):
    """Verifies that db.lock_user is safely re-entrant within the same asyncio Task."""
    user_id = "test_reentrant_user"
    async with fresh_db.lock_user(user_id):
        async with fresh_db.lock_user(user_id):
            assert True


@pytest.mark.asyncio
async def test_save_user_data_upsert_preserves_inventory(fresh_db):
    """Verifies save_user_data updates inventory without leaving zero-state windows."""
    user_id = "upsert_user"
    await fresh_db.ensure_user(user_id)

    user = await fresh_db.get_user_data(user_id)
    user["inventory"] = {"Common": 5, "Rare": 2}
    user["currencies"] = {"clovers": 100}
    await fresh_db.save_user_data(user_id, user)

    fetched = await fresh_db.get_user_data(user_id)
    assert fetched["inventory"]["Common"] == 5
    assert fetched["inventory"]["Rare"] == 2
    assert fetched["currencies"]["clovers"] == 100

    fetched["inventory"]["Common"] = 6
    fetched["inventory"]["Legendary"] = 1
    del fetched["inventory"]["Rare"]
    await fresh_db.save_user_data(user_id, fetched)

    updated = await fresh_db.get_user_data(user_id)
    assert updated["inventory"]["Common"] == 6
    assert updated["inventory"]["Legendary"] == 1
    assert "Rare" not in updated["inventory"]


@pytest.mark.asyncio
async def test_conversation_history_prunes_per_user(fresh_db):
    for i in range(50):
        await fresh_db.add_conversation_message(
            user_id="u7",
            guild_id=None,
            role="user",
            content=f"msg {i}",
            max_history=10,
        )

    async with fresh_db.conn.execute(
        "SELECT COUNT(*) FROM conversation_history WHERE user_id = ?", ("u7",)
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 10, f"Expected 10 rows, found {row[0]}"


@pytest.mark.asyncio
async def test_conversation_history_prunes_per_guild(fresh_db):
    for i in range(40):
        await fresh_db.add_conversation_message(
            user_id=None,
            guild_id="g1",
            role="user",
            content=f"g {i}",
            max_history=8,
        )
    async with fresh_db.conn.execute(
        "SELECT COUNT(*) FROM conversation_history WHERE guild_id = ?", ("g1",)
    ) as cur:
        row = await cur.fetchone()
    assert row[0] == 8


@pytest.mark.asyncio
async def test_get_messages_for_context_is_chronological(fresh_db):
    for i in range(5):
        await fresh_db.add_conversation_message(
            user_id="u8",
            guild_id=None,
            role="user",
            content=f"m{i}",
        )
    msgs = await fresh_db.get_messages_for_context(user_id="u8", limit=10)
    contents = [m["content"] for m in msgs]
    assert contents == ["m0", "m1", "m2", "m3", "m4"]


@pytest.mark.asyncio
async def test_clear_conversation_history(fresh_db):
    for i in range(3):
        await fresh_db.add_conversation_message(
            user_id="u9",
            guild_id=None,
            role="user",
            content=str(i),
        )
    ok = await fresh_db.clear_conversation_history(user_id="u9")
    assert ok is True
    msgs = await fresh_db.get_messages_for_context(user_id="u9", limit=10)
    assert msgs == []


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
async def test_regeneration_history_and_context_resolution(fresh_db, monkeypatch):
    """Verifies that get_context_for_message skips duplicate assistant entries and finds the true user prompt."""
    monkeypatch.setattr(utils, "db", fresh_db)

    user_id = "user_regen_test"
    guild_id = "guild_regen_test"

    await utils.append_message_for_context(
        user_id,
        False,
        "user",
        "What is the capital of France?",
        guild_id=guild_id,
        message_ids=[1001],
        author_id=user_id,
    )
    await utils.append_message_for_context(
        user_id, False, "assistant", "Paris is the capital.", guild_id=guild_id, message_ids=[1002]
    )
    await utils.append_message_for_context(
        user_id,
        False,
        "assistant",
        "Duplicate response without user prompt.",
        guild_id=guild_id,
        message_ids=[1003],
    )

    prompt, context = await fresh_db.get_context_for_message(user_id, False, guild_id, 1003)
    assert prompt == "What is the capital of France?"
    assert all(m["role"] in ["user", "assistant"] for m in context)

    updated = await fresh_db.update_message_in_history(
        user_id, False, guild_id, 1002, "Paris is indeed the capital.", new_message_ids=[1002, 1004]
    )
    assert updated is True

    history = await fresh_db.get_messages_for_context(
        guild_id=guild_id, limit=20, include_internal=True
    )
    assert len(history) == 3
    updated_row = next(m for m in history if 1002 in m["message_ids"])
    assert updated_row["content"] == "Paris is indeed the capital."
    assert 1004 in updated_row["message_ids"]


@pytest.mark.asyncio
async def test_user_params_roundtrip(fresh_db):
    await fresh_db.ensure_user_params("u13")
    await fresh_db.set_user_param("u13", "temperature", 0.42)
    params = await fresh_db.get_user_params("u13")
    assert params["temperature"] == 0.42


@pytest.mark.asyncio
async def test_default_persona_created(fresh_db):
    personas, active = await fresh_db.get_user_personas("u14")
    assert "Default" in personas
    assert active == "Default"


@pytest.mark.asyncio
async def test_persona_equip_and_edit(fresh_db):
    await fresh_db.get_user_personas("u15")
    assert await fresh_db.add_persona("u15", "Sassy", "user bio", "ai bio")
    assert await fresh_db.equip_persona("u15", "Sassy")
    params = await fresh_db.get_user_params("u15")
    assert params["active_persona"] == "Sassy"
    assert params["user_persona"] == "user bio"


@pytest.mark.asyncio
async def test_delete_active_persona_restores_default_params(fresh_db):
    """Verify deleting active persona restores Default persona's prompts in user_params."""
    user_id = "test_user_789"
    await fresh_db.ensure_user(int("789"))
    await fresh_db.add_persona(user_id, "Default", "Default user", "Default AI")

    await fresh_db.add_persona(user_id, "Pirate", "Ahoy matey", "Talk like a pirate")
    await fresh_db.equip_persona(user_id, "Pirate")

    params = await fresh_db.get_user_params(user_id)
    assert params["active_persona"] == "Pirate"
    assert params["ai_persona"] == "Talk like a pirate"

    deleted = await fresh_db.delete_persona(user_id, "Pirate")
    assert deleted is True

    new_params = await fresh_db.get_user_params(user_id)
    assert new_params["active_persona"] == "Default"
    assert new_params["ai_persona"] == "Default AI"
    assert new_params["user_persona"] == "Default user"
