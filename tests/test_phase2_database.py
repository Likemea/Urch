# tests/test_phase2_database.py
"""
Phase 2 — Database.
Exercises the Database class, transaction/lock semantics, and the utils
currency/roll helpers against an isolated SQLite file.
"""
import asyncio
import pytest
import pytest_asyncio


# ── 2.1 User lifecycle ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ensure_user_and_get(fresh_db):
    created = await fresh_db.ensure_user("u1")
    assert created is True
    # Second call should be a no-op
    created_again = await fresh_db.ensure_user("u1")
    assert created_again is False

    data = await fresh_db.get_user_data("u1")
    assert data is not None
    assert data["roll_count"] == 0
    assert data["luck_multi"] == 1.0


@pytest.mark.asyncio
async def test_get_unknown_user_returns_none(fresh_db):
    assert await fresh_db.get_user_data("nobody") is None


# ── 2.2 Transaction semantics ─────────────────────────────────────────────────
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
        await fresh_db.conn.execute(
            "UPDATE users SET roll_count = 42 WHERE user_id = ?", ("u3",)
        )
    data = await fresh_db.get_user_data("u3")
    assert data["roll_count"] == 42


# ── 2.3 Per-user lock serializes concurrent access ────────────────────────────
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
    # Starts and ends must not interleave
    assert events in (
        ["start-1", "end-1", "start-2", "end-2"],
        ["start-2", "end-2", "start-1", "end-1"],
    ), f"Locks leaked: {events}"


# ── 2.4 Currency / inventory helpers ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_currency_add_remove_roundtrip(fresh_db):
    from utils import currency_add, currency_remove, currency_count
    await fresh_db.ensure_user("u5")

    await currency_add("u5", "clovers", 10)
    assert await currency_count("u5", "clovers") == 10

    assert await currency_remove("u5", "clovers", 4) is True
    assert await currency_count("u5", "clovers") == 6

    # Removing more than available returns False and does not mutate
    assert await currency_remove("u5", "clovers", 999) is False
    assert await currency_count("u5", "clovers") == 6


@pytest.mark.asyncio
async def test_inventory_vs_currency_routing(fresh_db):
    """`resolve_item_key` must route names/ids to inventory and the rest to currency."""
    from utils import currency_add, currency_count
    from raritylist import RARITIES

    await fresh_db.ensure_user("u6")
    rarity_name = RARITIES[0][0]

    await currency_add("u6", rarity_name, 3)
    await currency_add("u6", "clovers", 5)

    data = await fresh_db.get_user_data("u6")
    assert data["inventory"].get(rarity_name) == 3
    assert data["currencies"].get("clovers") == 5


# ── 2.5 Conversation history and pruning ──────────────────────────────────────
@pytest.mark.asyncio
async def test_conversation_history_prunes_per_user(fresh_db):
    """After the bug-2 fix, add_conversation_message must cap history."""
    for i in range(50):
        await fresh_db.add_conversation_message(
            user_id="u7", guild_id=None,
            role="user", content=f"msg {i}",
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
            user_id=None, guild_id="g1",
            role="user", content=f"g {i}",
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
            user_id="u8", guild_id=None, role="user", content=f"m{i}",
        )
    msgs = await fresh_db.get_messages_for_context(user_id="u8", limit=10)
    contents = [m["content"] for m in msgs]
    assert contents == ["m0", "m1", "m2", "m3", "m4"]


@pytest.mark.asyncio
async def test_clear_conversation_history(fresh_db):
    for i in range(3):
        await fresh_db.add_conversation_message(
            user_id="u9", guild_id=None, role="user", content=str(i),
        )
    ok = await fresh_db.clear_conversation_history(user_id="u9")
    assert ok is True
    msgs = await fresh_db.get_messages_for_context(user_id="u9", limit=10)
    assert msgs == []


# ── 2.6 Rolling ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_roll_rarities_returns_valid_names(fresh_db):
    from utils import roll_rarities
    from raritylist import RARITY_NAMES

    await fresh_db.ensure_user("u10")
    results = await roll_rarities("u10", count=25, provided_luck=1.0)
    assert len(results) == 25
    assert all(r in RARITY_NAMES for r in results)


@pytest.mark.asyncio
async def test_roll_rarities_high_luck_biases_rarity(fresh_db):
    """High luck should not produce *worse* average rank than low luck."""
    from utils import roll_rarities
    from raritylist import RARITIES

    await fresh_db.ensure_user("u11")
    order = {r[0]: i for i, r in enumerate(RARITIES)}

    low = await roll_rarities("u11", count=500, provided_luck=1.0)
    high = await roll_rarities("u11", count=500, provided_luck=1000.0)

    avg_low = sum(order[r] for r in low) / len(low)
    avg_high = sum(order[r] for r in high) / len(high)
    assert avg_high >= avg_low, (
        f"Luck inversion: low={avg_low:.2f} high={avg_high:.2f}"
    )


# ── 2.7 Autoroll ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_process_autorolls_does_not_crash(fresh_db):
    from utils import process_autorolls
    await fresh_db.ensure_user("u12")
    await fresh_db.set_autoroll_status("u12", True)

    # Should return a list (rare hits), possibly empty
    rare_hits = await process_autorolls(["u12"])
    assert isinstance(rare_hits, list)

    data = await fresh_db.get_user_data("u12")
    assert data["roll_count"] >= 1, "Autoroll did not increment roll_count"


# ── 2.8 User params roundtrip ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_user_params_roundtrip(fresh_db):
    await fresh_db.ensure_user_params("u13")
    await fresh_db.set_user_param("u13", "temperature", 0.42)
    params = await fresh_db.get_user_params("u13")
    assert params["temperature"] == 0.42


# ── 2.9 Personas ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_default_persona_created(fresh_db):
    personas, active = await fresh_db.get_user_personas("u14")
    assert "Default" in personas
    assert active == "Default"


@pytest.mark.asyncio
async def test_persona_equip_and_edit(fresh_db):
    await fresh_db.get_user_personas("u15")  # ensure Default exists
    assert await fresh_db.add_persona("u15", "Sassy", "user bio", "ai bio")
    assert await fresh_db.equip_persona("u15", "Sassy")
    params = await fresh_db.get_user_params("u15")
    assert params["active_persona"] == "Sassy"
    assert params["user_persona"] == "user bio"