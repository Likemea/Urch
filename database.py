# Urch/database.py
import aiosqlite
import asyncio
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
import logging
import contextlib

logger = logging.getLogger(__name__)


class ReentrantLock:
    """Asyncio lock that can be safely re-entered by the same asyncio.Task."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner: Optional[asyncio.Task] = None
        self._depth = 0

    async def acquire(self):
        curr = asyncio.current_task()
        if self._owner is curr:
            self._depth += 1
            return
        await self._lock.acquire()
        self._owner = curr
        self._depth = 1

    def release(self):
        curr = asyncio.current_task()
        if self._owner is not curr:
            raise RuntimeError("Cannot release un-acquired lock")
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def locked(self) -> bool:
        return self._lock.locked()


DB_PATH = "bot_data.db"
VALID_PARAM_COLUMNS = {
    "max_completion_tokens",
    "temperature",
    "top_p",
    "model",
    "reasoning",
    "tooling",
    "user_persona",
    "ai_persona",
    "active_persona",
    "last_summary_time",
}


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._lock = ReentrantLock()
        self._tx_depth = 0
        self._user_locks: Dict[str, Any] = {}
        self._lock_usage: Dict[str, datetime] = {}
        self._user_lock_refcount: Dict[str, int] = {}
        self._cleanup_lock = asyncio.Lock()

    async def initialize(self):
        """Initialize database and create tables"""
        if self.conn is not None:
            return
        self.conn = await aiosqlite.connect(self.db_path)
        async with self.conn.execute("PRAGMA journal_mode=WAL"):
            pass
        async with self.conn.execute("PRAGMA synchronous=NORMAL"):
            pass
        async with self.conn.execute("PRAGMA foreign_keys=ON"):
            pass
        self.conn.row_factory = aiosqlite.Row
        # Users table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                roll_count INTEGER DEFAULT 0,
                highscore TEXT,
                luck_multi REAL DEFAULT 1.0,
                max_luck REAL DEFAULT 1.0,
                clover_multi REAL DEFAULT 1.0,
                clover_every INTEGER DEFAULT 10,
                clovers_earned INTEGER DEFAULT 0,
                luck_override REAL,
                autoroll_active BOOLEAN DEFAULT 0
            )
        """):
            pass

        try:
            async with self.conn.execute(
                "ALTER TABLE users ADD COLUMN autoroll_active BOOLEAN DEFAULT 0"
            ):
                pass
            await self.conn.commit()
        except aiosqlite.OperationalError:
            pass

        # User inventory table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                discovered BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (user_id, item_name)
            )
        """):
            pass

        # User upgrades table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_upgrades (
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                upgrade_key TEXT NOT NULL,
                tier INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, category, upgrade_key)
            )
        """):
            pass

        # User currencies table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_currencies (
                user_id TEXT NOT NULL,
                currency_type TEXT NOT NULL,
                amount INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, currency_type)
            )
        """):
            pass

        # User parameters table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_params (
                user_id TEXT PRIMARY KEY,
                max_completion_tokens INTEGER DEFAULT 1000,
                temperature REAL DEFAULT 0.75,
                top_p REAL DEFAULT 1.0,
                model TEXT DEFAULT 'Auto',
                reasoning TEXT DEFAULT 'none',
                tooling TEXT DEFAULT 'Auto',
                user_persona TEXT DEFAULT '',
                ai_persona TEXT DEFAULT '',
                active_persona TEXT DEFAULT 'Default',
                last_summary_time TEXT
            )
        """):
            pass

        try:
            async with self.conn.execute(
                "ALTER TABLE user_params ADD COLUMN tooling TEXT DEFAULT 'Auto'"
            ):
                pass
            await self.conn.commit()
        except aiosqlite.OperationalError:
            pass

        # User personas table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_personas (
                user_id TEXT NOT NULL,
                persona_name TEXT NOT NULL,
                user_persona TEXT DEFAULT '',
                ai_persona TEXT DEFAULT '',
                PRIMARY KEY (user_id, persona_name)
            )
        """):
            pass

        # Conversation history table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                channel_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message_ids TEXT,
                author_id TEXT
            )
        """):
            pass

        async with self.conn.execute("PRAGMA table_info(conversation_history)") as cur:
            cols = [r["name"] for r in await cur.fetchall()]
            if "channel_id" not in cols:
                await self.conn.execute(
                    "ALTER TABLE conversation_history ADD COLUMN channel_id TEXT"
                )

        # indexes for performance
        async with self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_user_time 
            ON conversation_history (user_id, timestamp)
        """):
            pass
        async with self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_guild_time 
            ON conversation_history (guild_id, timestamp)
        """):
            pass
        async with self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_channel_time 
            ON conversation_history (channel_id, timestamp)
        """):
            pass
        async with self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_user 
            ON user_inventory (user_id, item_name)
        """):
            pass

        # meaningful rolls table
        async with self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rare_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                rarity_name TEXT NOT NULL,
                one_in REAL NOT NULL,
                total_luck REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        """):
            pass
        async with self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rare_hits_user ON rare_hits (user_id, timestamp)"
        ):
            pass

        await self.conn.commit()
        await self._sanitize_glitched_potions()
        logger.info("Database initialized successfully")

    async def _commit_if_not_in_tx(self):
        if self._tx_depth == 0:
            await self.conn.commit()

    @contextlib.asynccontextmanager
    async def transaction(self):
        """Custom async context manager for aiosqlite transactions.
        Ensures connection initialization, serializes via self._lock,
        and supports nested transactions via SQLite savepoints."""
        await self._check_conn()
        async with self._lock:
            self._tx_depth += 1
            depth = self._tx_depth
            savepoint = f"sp_{depth}"
            try:
                if depth > 1:
                    await self.conn.execute(f"SAVEPOINT {savepoint}")
                yield
                if depth == 1:
                    await self.conn.commit()
                else:
                    await self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except BaseException:
                if depth == 1:
                    await self.conn.rollback()
                else:
                    await self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    await self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._tx_depth -= 1

    @contextlib.asynccontextmanager
    async def lock_user(self, user_id: str):
        """Asynchronous context manager for per-user locking (re-entrant per task)"""
        uid = str(user_id)
        async with self._cleanup_lock:
            if uid not in self._user_locks:
                self._user_locks[uid] = ReentrantLock()
                self._user_lock_refcount[uid] = 0
            self._user_lock_refcount[uid] += 1
            lock = self._user_locks[uid]
            self._lock_usage[uid] = datetime.now()

        try:
            async with lock:
                yield
        finally:
            async with self._cleanup_lock:
                self._lock_usage[uid] = datetime.now()
                self._user_lock_refcount[uid] = max(0, self._user_lock_refcount.get(uid, 1) - 1)

            if len(self._user_locks) > 100:
                asyncio.create_task(self._cleanup_locks())

    async def _cleanup_locks(self):
        """Internal: Clean up old locks that haven't been used in a while"""
        async with self._cleanup_lock:
            now = datetime.now()
            threshold = now - timedelta(hours=1)
            to_delete = [
                uid
                for uid, last_used in list(self._lock_usage.items())
                if last_used < threshold
                and uid in self._user_locks
                and self._user_lock_refcount.get(uid, 0) == 0
                and not self._user_locks[uid].locked()
            ]
            for uid in to_delete:
                self._user_locks.pop(uid, None)
                self._lock_usage.pop(uid, None)
                self._user_lock_refcount.pop(uid, None)

    async def _sanitize_glitched_potions(self):
        """One-time / startup normalization for glitched potion durations and charges."""
        try:
            now = int(datetime.now(timezone.utc).timestamp())
            MAX_DURATION_SECONDS = 86400  # 24 hours max active duration
            MAX_CHARGES = 1000

            async with self._lock:
                async with self.conn.execute(
                    "SELECT user_id, currency_type, amount FROM user_currencies WHERE currency_type LIKE 'potion_%'"
                ) as cursor:
                    rows = await cursor.fetchall()

                updates = []
                for row in rows:
                    user_id = row["user_id"]
                    curr_type = row["currency_type"]
                    amount = row["amount"]

                    if curr_type.startswith("potion_exp_"):
                        # Expired potion: clean up
                        if 0 < amount <= now:
                            updates.append((0, user_id, curr_type))
                        # Duration exceeds max limit (24 hours): clamp to max duration from now
                        elif amount > now + MAX_DURATION_SECONDS:
                            new_exp = now + MAX_DURATION_SECONDS
                            updates.append((new_exp, user_id, curr_type))

                    elif curr_type.startswith("potion_charge_"):
                        # Charge exceeds max limit: clamp to 1000 charges
                        if amount > MAX_CHARGES:
                            updates.append((MAX_CHARGES, user_id, curr_type))
                        elif amount <= 0:
                            updates.append((0, user_id, curr_type))

                if updates:
                    for new_val, uid, ctype in updates:
                        if new_val == 0:
                            await self.conn.execute(
                                "DELETE FROM user_currencies WHERE user_id = ? AND currency_type = ?",
                                (uid, ctype),
                            )
                        else:
                            await self.conn.execute(
                                "UPDATE user_currencies SET amount = ? WHERE user_id = ? AND currency_type = ?",
                                (new_val, uid, ctype),
                            )
                    await self._commit_if_not_in_tx()
                    logger.info(f"Sanitized {len(updates)} glitched potion entries in database.")
        except Exception as e:
            logger.warning(f"Error while sanitizing glitched potions: {e}")

    async def _check_conn(self):
        if not self.conn:
            await self.initialize()

    # --- User Data ---

    async def ensure_user(self, user_id: str) -> bool:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
            ) as cursor:
                await self._commit_if_not_in_tx()
                return cursor.rowcount > 0

    async def get_user_currencies(self, user_id: str) -> Dict[str, int]:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT currency_type, amount FROM user_currencies WHERE user_id = ?", (user_id,)
            ) as cursor:
                return {
                    row["currency_type"]: row["amount"]
                    async for row in cursor
                    if row["amount"] > 0
                }

    async def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                user_row = await cursor.fetchone()
                if not user_row:
                    return None
                user_data = dict(user_row)

            async with self.conn.execute(
                "SELECT item_name, quantity, discovered FROM user_inventory WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                inventory = {}
                discovered = {}
                async for row in cursor:
                    if row["quantity"] > 0:
                        inventory[row["item_name"]] = row["quantity"]
                    discovered[row["item_name"]] = bool(row["discovered"])
                user_data["inventory"] = inventory
                user_data["discovered"] = discovered

            async with self.conn.execute(
                "SELECT category, upgrade_key, tier FROM user_upgrades WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                upgrades = {"luck": {}, "roll": {}, "clover": {}}
                async for row in cursor:
                    if row["category"] not in upgrades:
                        upgrades[row["category"]] = {}
                    upgrades[row["category"]][row["upgrade_key"]] = row["tier"]
                user_data["upgrades"] = upgrades

            async with self.conn.execute(
                "SELECT currency_type, amount FROM user_currencies WHERE user_id = ?", (user_id,)
            ) as cursor:
                currencies = {}
                async for row in cursor:
                    if row["amount"] > 0:
                        currencies[row["currency_type"]] = row["amount"]
                user_data["currencies"] = currencies

            return user_data

    async def save_user_data(self, user_id: str, data: Dict[str, Any]):
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                async with self.conn.execute(
                    """
                    INSERT OR REPLACE INTO users 
                    (user_id, roll_count, highscore, luck_multi, max_luck, clover_multi, 
                        clover_every, clovers_earned, luck_override, autoroll_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        data.get("roll_count", 0),
                        data.get("highscore"),
                        data.get("luck_multi", 1.0),
                        data.get("max_luck", 1.0),
                        data.get("clover_multi", 1.0),
                        data.get("clover_every", 10),
                        data.get("clovers_earned", 0),
                        data.get("luck_override"),
                        data.get("autoroll_active", 0),
                    ),
                ):
                    pass

                if "inventory" in data or "discovered" in data:
                    all_items = set(data.get("inventory", {}).keys()) | set(
                        data.get("discovered", {}).keys()
                    )
                    if all_items:
                        inv_rows = [
                            (
                                user_id,
                                item_name,
                                data.get("inventory", {}).get(item_name, 0),
                                1 if data.get("discovered", {}).get(item_name, False) else 0,
                            )
                            for item_name in all_items
                        ]
                        await self.conn.executemany(
                            """
                            INSERT INTO user_inventory (user_id, item_name, quantity, discovered)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(user_id, item_name) DO UPDATE SET
                                quantity = excluded.quantity,
                                discovered = excluded.discovered
                            """,
                            inv_rows,
                        )
                        placeholders = ",".join("?" for _ in all_items)
                        await self.conn.execute(
                            f"DELETE FROM user_inventory WHERE user_id = ? AND item_name NOT IN ({placeholders})",
                            (user_id, *all_items),
                        )
                    else:
                        await self.conn.execute(
                            "DELETE FROM user_inventory WHERE user_id = ?", (user_id,)
                        )
                    # Targeted delete for zero/negative quantity and not discovered
                    await self.conn.execute(
                        "DELETE FROM user_inventory WHERE user_id = ? AND quantity <= 0 AND discovered = 0",
                        (user_id,),
                    )

                if "upgrades" in data and data["upgrades"]:
                    upg_rows = [
                        (user_id, category, upgrade_key, tier)
                        for category, upgrades in data["upgrades"].items()
                        for upgrade_key, tier in upgrades.items()
                    ]
                    if upg_rows:
                        await self.conn.executemany(
                            "INSERT OR REPLACE INTO user_upgrades (user_id, category, upgrade_key, tier) VALUES (?, ?, ?, ?)",
                            upg_rows,
                        )

                if "currencies" in data:
                    currencies = data.get("currencies", {})
                    if currencies:
                        curr_rows = [
                            (user_id, currency_type, amount)
                            for currency_type, amount in currencies.items()
                        ]
                        await self.conn.executemany(
                            """
                            INSERT INTO user_currencies (user_id, currency_type, amount)
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id, currency_type) DO UPDATE SET
                                amount = excluded.amount
                            """,
                            curr_rows,
                        )
                        placeholders = ",".join("?" for _ in currencies.keys())
                        await self.conn.execute(
                            f"DELETE FROM user_currencies WHERE user_id = ? AND currency_type NOT IN ({placeholders})",
                            (user_id, *currencies.keys()),
                        )
                    else:
                        await self.conn.execute(
                            "DELETE FROM user_currencies WHERE user_id = ?", (user_id,)
                        )
                    # Targeted delete for zero/negative currencies
                    await self.conn.execute(
                        "DELETE FROM user_currencies WHERE user_id = ? AND amount <= 0",
                        (user_id,),
                    )

    async def get_active_rollers(self) -> List[str]:
        """Fetch all user IDs with autoroll enabled"""
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT user_id FROM users WHERE autoroll_active = 1"
            ) as cursor:
                return [row["user_id"] async for row in cursor]

    async def set_autoroll_status(self, user_id: str, active: bool):
        """Enable or disable autoroll for a user"""
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "UPDATE users SET autoroll_active = ? WHERE user_id = ?",
                (1 if active else 0, user_id),
            ):
                await self._commit_if_not_in_tx()

    async def bulk_update_autoroll(self, updates: List[Dict[str, Any]]):
        """Bulk update user data for autoroll processing"""
        if not updates:
            return
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                for up in updates:
                    user_id = up["user_id"]
                    # Update users table
                    async with self.conn.execute(
                        """
                        UPDATE users SET 
                            roll_count = ?, 
                            highscore = ?, 
                            luck_multi = ?, 
                            max_luck = ?,
                            clovers_earned = ?
                        WHERE user_id = ?
                    """,
                        (
                            up["roll_count"],
                            up["highscore"],
                            up["luck_multi"],
                            up["max_luck"],
                            up["clovers_earned"],
                            user_id,
                        ),
                    ):
                        pass

                    # Update inventory
                    for item_name, quantity_diff in up.get("inventory_diff", {}).items():
                        async with self.conn.execute(
                            """
                            INSERT INTO user_inventory (user_id, item_name, quantity, discovered)
                            VALUES (?, ?, ?, 1)
                            ON CONFLICT(user_id, item_name) DO UPDATE SET
                            quantity = quantity + excluded.quantity,
                            discovered = 1
                        """,
                            (user_id, item_name, quantity_diff),
                        ):
                            pass

                    # Update currencies
                    for curr_type, amount_diff in up.get("currency_diff", {}).items():
                        async with self.conn.execute(
                            """
                            INSERT INTO user_currencies (user_id, currency_type, amount)
                            VALUES (?, ?, ?)
                            ON CONFLICT(user_id, currency_type) DO UPDATE SET
                            amount = amount + excluded.amount
                        """,
                            (user_id, curr_type, amount_diff),
                        ):
                            pass

    async def add_rare_hit(self, user_id: str, rarity_name: str, one_in: float, total_luck: float):
        """Store a meaningful roll in the database"""
        await self._check_conn()
        timestamp = datetime.now(timezone.utc).isoformat()
        async with self._lock:
            async with self.transaction():
                async with self.conn.execute(
                    """
                    INSERT INTO rare_hits (user_id, rarity_name, one_in, total_luck, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (user_id, rarity_name, one_in, total_luck, timestamp),
                ):
                    pass
                async with self.conn.execute(
                    """
                    DELETE FROM rare_hits WHERE id NOT IN (
                        SELECT id FROM rare_hits WHERE user_id = ? ORDER BY timestamp DESC LIMIT 100
                    ) AND user_id = ?
                """,
                    (user_id, user_id),
                ):
                    pass

    async def get_recent_rare_hits(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch the most recent rare rolls for a user"""
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                """
                SELECT rarity_name, one_in, total_luck, timestamp 
                FROM rare_hits 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (user_id, limit),
            ) as cursor:
                return [dict(row) async for row in cursor]

    # --- User Parameters ---

    async def ensure_user_params(self, user_id: str):
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "INSERT OR IGNORE INTO user_params (user_id) VALUES (?)", (user_id,)
            ):
                await self._commit_if_not_in_tx()

    async def get_user_params(self, user_id: str) -> Dict[str, Any]:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT * FROM user_params WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else self._get_default_params()

    def _get_default_params(self) -> Dict[str, Any]:
        return {
            "max_completion_tokens": 1000,
            "temperature": 0.75,
            "top_p": 1.0,
            "model": "Auto",
            "reasoning": "none",
            "tooling": "Auto",
            "user_persona": "",
            "ai_persona": "",
            "active_persona": "Default",
            "last_summary_time": None,
        }

    async def set_user_params(self, user_id: str, params: Dict[str, Any]):
        """Set user parameters"""
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                """
                INSERT OR REPLACE INTO user_params 
                (user_id, max_completion_tokens, temperature, top_p, model, reasoning, tooling,
                 user_persona,
                 ai_persona, active_persona, last_summary_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    params.get("max_completion_tokens", 1000),
                    params.get("temperature", 0.75),
                    params.get("top_p", 1.0),
                    params.get("model", "Auto"),
                    params.get("reasoning", "none"),
                    params.get("tooling", "Auto"),
                    params.get("user_persona", ""),
                    params.get("ai_persona", ""),
                    params.get("active_persona", "Default"),
                    params.get("last_summary_time"),
                ),
            ):
                await self._commit_if_not_in_tx()

    async def set_user_param(self, user_id: str, param_name: str, value: Any):
        if param_name not in VALID_PARAM_COLUMNS:
            raise ValueError(f"Invalid user_params column: {param_name}")
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                f"UPDATE user_params SET {param_name} = ? WHERE user_id = ?", (value, user_id)
            ):
                await self._commit_if_not_in_tx()

    async def get_user_personas(self, user_id: str) -> Tuple[Dict[str, Dict[str, str]], str]:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT active_persona FROM user_params WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                active = row["active_persona"] if row else "Default"

            personas = {}
            async with self.conn.execute(
                "SELECT * FROM user_personas WHERE user_id = ?", (user_id,)
            ) as cur:
                async for row in cur:
                    personas[row["persona_name"]] = {
                        "user_persona": row["user_persona"],
                        "ai_persona": row["ai_persona"],
                    }

            if "Default" not in personas:
                personas["Default"] = {"user_persona": "", "ai_persona": ""}
                await self.add_persona(user_id, "Default", "", "")
            return personas, active

    async def add_persona(self, user_id: str, name: str, user_p: str, ai_p: str) -> bool:
        await self._check_conn()
        async with self._lock:
            try:
                async with self.conn.execute(
                    "INSERT INTO user_personas (user_id, persona_name, user_persona, ai_persona) VALUES (?, ?, ?, ?)",
                    (user_id, name, user_p, ai_p),
                ):
                    await self._commit_if_not_in_tx()
                    return True
            except aiosqlite.IntegrityError:
                return False

    async def delete_persona(self, user_id: str, name: str) -> bool:
        """Delete a persona"""
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                # Check if it's the last persona
                async with self.conn.execute(
                    "SELECT COUNT(*) as count FROM user_personas WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row["count"] <= 1:
                        return False

                # Delete the persona
                async with self.conn.execute(
                    "DELETE FROM user_personas WHERE user_id = ? AND persona_name = ?",
                    (user_id, name),
                ):
                    pass

                # If it was active, set Default as active
                async with self.conn.execute(
                    "SELECT active_persona FROM user_params WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row["active_persona"] == name:
                        async with self.conn.execute(
                            "SELECT user_persona, ai_persona FROM user_personas WHERE user_id = ? AND persona_name = 'Default'",
                            (user_id,),
                        ) as def_cursor:
                            def_row = await def_cursor.fetchone()
                        def_user_p = def_row["user_persona"] if def_row else ""
                        def_ai_p = def_row["ai_persona"] if def_row else ""
                        async with self.conn.execute(
                            "UPDATE user_params SET active_persona = ?, user_persona = ?, ai_persona = ? WHERE user_id = ?",
                            ("Default", def_user_p, def_ai_p, user_id),
                        ):
                            pass

                return True

    async def equip_persona(self, user_id: str, name: str) -> bool:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute(
                "SELECT user_persona, ai_persona FROM user_personas WHERE user_id=? AND persona_name=?",
                (user_id, name),
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return False

                async with self.conn.execute(
                    """
                    INSERT INTO user_params (user_id, active_persona, user_persona, ai_persona)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        active_persona = excluded.active_persona,
                        user_persona = excluded.user_persona,
                        ai_persona = excluded.ai_persona
                    """,
                    (user_id, name, row[0], row[1]),
                ):
                    await self._commit_if_not_in_tx()
                    return True

    async def edit_persona(self, user_id: str, name: str, user_p: str, ai_p: str) -> bool:
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                async with self.conn.execute(
                    "UPDATE user_personas SET user_persona=?, ai_persona=? WHERE user_id=? AND persona_name=?",
                    (user_p, ai_p, user_id, name),
                ):
                    pass
                # Also update if its the currently active one
                async with self.conn.execute(
                    """
                    UPDATE user_params SET user_persona=?, ai_persona=? 
                    WHERE user_id=? AND active_persona=?
                """,
                    (user_p, ai_p, user_id, name),
                ):
                    pass
                return True

    # --- Conversation History ---

    async def add_conversation_message(
        self,
        user_id: str,
        guild_id: str,
        role: str,
        content: str,
        message_ids: list = None,
        author_id: str = None,
        max_history: int = 20,
        channel_id: str = None,
    ):
        await self._check_conn()
        timestamp = datetime.now(timezone.utc).isoformat()
        msg_ids_json = json.dumps(message_ids) if message_ids else None

        async with self._lock:
            async with self.transaction():
                async with self.conn.execute(
                    """
                    INSERT INTO conversation_history
                    (user_id, guild_id, channel_id, role, content, timestamp, message_ids, author_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        guild_id,
                        str(channel_id) if channel_id else None,
                        role,
                        content,
                        timestamp,
                        msg_ids_json,
                        author_id,
                    ),
                ):
                    pass

                if channel_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history
                            WHERE channel_id = ? ORDER BY id DESC LIMIT ?
                        ) AND channel_id = ?
                    """,
                        (str(channel_id), max_history, str(channel_id)),
                    ):
                        pass
                elif user_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history
                            WHERE user_id = ? ORDER BY id DESC LIMIT ?
                        ) AND user_id = ?
                    """,
                        (user_id, max_history, user_id),
                    ):
                        pass
                elif guild_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history
                            WHERE guild_id = ? ORDER BY id DESC LIMIT ?
                        ) AND guild_id = ?
                    """,
                        (guild_id, max_history, guild_id),
                    ):
                        pass

    async def append_message(
        self,
        user_id,
        guild_id,
        role,
        content,
        message_ids=None,
        author_id=None,
        max_history=20,
        channel_id=None,
    ):
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                async with self.conn.execute(
                    """
                    INSERT INTO conversation_history (user_id, guild_id, channel_id, role, content, timestamp, message_ids, author_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        guild_id,
                        str(channel_id) if channel_id else None,
                        role,
                        content,
                        datetime.now().isoformat(),
                        json.dumps(message_ids) if message_ids else None,
                        author_id,
                    ),
                ):
                    pass

                # --- Prune old messages beyond max_history ---
                if channel_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history WHERE channel_id = ? ORDER BY id DESC LIMIT ?
                        ) AND channel_id = ?
                    """,
                        (str(channel_id), max_history, str(channel_id)),
                    ):
                        pass
                elif user_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history WHERE user_id = ? ORDER BY id DESC LIMIT ?
                        ) AND user_id = ?
                    """,
                        (user_id, max_history, user_id),
                    ):
                        pass
                elif guild_id:
                    async with self.conn.execute(
                        """
                        DELETE FROM conversation_history WHERE id NOT IN (
                            SELECT id FROM conversation_history WHERE guild_id = ? ORDER BY id DESC LIMIT ?
                        ) AND guild_id = ?
                    """,
                        (guild_id, max_history, guild_id),
                    ):
                        pass

    async def get_messages_for_context(
        self,
        user_id=None,
        guild_id=None,
        limit=10,
        include_internal=False,
        read_only=True,
        channel_id=None,
    ):
        await self._check_conn()
        if channel_id:
            sql = "SELECT * FROM conversation_history WHERE channel_id = ? ORDER BY id DESC LIMIT ?"
            params = (str(channel_id), limit)
        elif user_id and guild_id:
            sql = "SELECT * FROM conversation_history WHERE user_id = ? OR guild_id = ? ORDER BY id DESC LIMIT ?"
            params = (user_id, guild_id, limit)
        elif user_id:
            sql = "SELECT * FROM conversation_history WHERE user_id = ? ORDER BY id DESC LIMIT ?"
            params = (user_id, limit)
        elif guild_id:
            sql = "SELECT * FROM conversation_history WHERE guild_id = ? ORDER BY id DESC LIMIT ?"
            params = (guild_id, limit)
        else:
            return []

        async with self._lock:
            async with self.conn.execute(sql, params) as cur:
                rows = await cur.fetchall()
        msgs = []
        for row in reversed(rows):  # chronological
            m = {"role": row["role"], "content": row["content"]}
            if include_internal:
                raw_ids = json.loads(row["message_ids"] or "[]")
                clean_ids = [int(x) if str(x).isdigit() else str(x) for x in raw_ids]
                m.update(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "message_ids": clean_ids,
                        "author_id": row["author_id"],
                        "channel_id": row["channel_id"] if "channel_id" in row.keys() else None,
                    }
                )
            msgs.append(m)
        return msgs

    async def update_message_in_history(
        self,
        user_id,
        is_dm,
        guild_id,
        message_id,
        new_content,
        new_message_ids=None,
        channel_id=None,
    ):
        await self._check_conn()
        if channel_id:
            sql = "SELECT id, message_ids FROM conversation_history WHERE channel_id=? ORDER BY id DESC LIMIT 50"
            params = (str(channel_id),)
        elif is_dm:
            sql = "SELECT id, message_ids FROM conversation_history WHERE user_id=? AND guild_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (user_id,)
        else:
            sql = "SELECT id, message_ids FROM conversation_history WHERE guild_id=? AND user_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (guild_id,)

        async with self._lock:
            async with self.conn.execute(sql, params) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids or str(message_id) in [str(x) for x in ids]:
                        if new_message_ids is not None:
                            clean_ids = [
                                int(mid) if str(mid).isdigit() else str(mid)
                                for mid in new_message_ids
                            ]
                            ids_json = json.dumps(clean_ids)
                            async with self.conn.execute(
                                "UPDATE conversation_history SET content=?, message_ids=? WHERE id=?",
                                (new_content, ids_json, row["id"]),
                            ):
                                await self._commit_if_not_in_tx()
                                return True
                        else:
                            async with self.conn.execute(
                                "UPDATE conversation_history SET content=? WHERE id=?",
                                (new_content, row["id"]),
                            ):
                                await self._commit_if_not_in_tx()
                                return True
        return False

    async def delete_message_from_history(
        self, user_id, is_dm, guild_id, message_id, channel_id=None
    ):
        await self._check_conn()
        if channel_id:
            sql = "SELECT id, message_ids FROM conversation_history WHERE channel_id=? ORDER BY id DESC LIMIT 50"
            params = (str(channel_id),)
        elif is_dm:
            sql = "SELECT id, message_ids FROM conversation_history WHERE user_id=? AND guild_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (user_id,)
        else:
            sql = "SELECT id, message_ids FROM conversation_history WHERE guild_id=? AND user_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (guild_id,)
        deleted_ids = []
        async with self._lock:
            async with self.conn.execute(sql, params) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids or str(message_id) in [str(x) for x in ids]:
                        deleted_ids = ids
                        async with self.conn.execute(
                            "DELETE FROM conversation_history WHERE id=?", (row["id"],)
                        ):
                            await self._commit_if_not_in_tx()
                            return deleted_ids or [message_id]
        return deleted_ids

    async def get_message_ids_for_reply(
        self, user_id, is_dm, guild_id, message_id, channel_id=None
    ):
        await self._check_conn()
        if channel_id:
            sql = "SELECT id, message_ids FROM conversation_history WHERE channel_id=? ORDER BY id DESC LIMIT 50"
            params = (str(channel_id),)
        elif is_dm:
            sql = "SELECT id, message_ids FROM conversation_history WHERE user_id=? AND guild_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (user_id,)
        else:
            sql = "SELECT id, message_ids FROM conversation_history WHERE guild_id=? AND user_id IS NULL ORDER BY id DESC LIMIT 50"
            params = (guild_id,)
        async with self._lock:
            async with self.conn.execute(sql, params) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids or str(message_id) in [str(x) for x in ids]:
                        return ids
        return [message_id]

    async def delete_messages_from_history_bulk(self, guild_id: str, message_ids: List[int]) -> int:
        """Delete multiple history rows based on a list of Discord message IDs"""
        if not message_ids:
            return 0

        await self._check_conn()
        deleted_count = 0
        target_set = set(message_ids)

        async with self._lock:
            async with self.transaction():
                # we fetch all rows for the guild to check their message_ids JSON
                async with self.conn.execute(
                    "SELECT id, message_ids FROM conversation_history WHERE guild_id = ?",
                    (str(guild_id),),
                ) as cursor:
                    rows_to_delete = []
                    async for row in cursor:
                        if row["message_ids"]:
                            try:
                                ids = json.loads(row["message_ids"])
                                if any(mid in target_set for mid in ids):
                                    rows_to_delete.append(row["id"])
                            except:
                                continue

                    if rows_to_delete:
                        for i in range(0, len(rows_to_delete), 500):
                            chunk = rows_to_delete[i : i + 500]
                            placeholders = ",".join("?" for _ in chunk)
                            async with self.conn.execute(
                                f"DELETE FROM conversation_history WHERE id IN ({placeholders})",
                                chunk,
                            ) as del_cursor:
                                deleted_count += del_cursor.rowcount
        return deleted_count

    async def clear_conversation_history(
        self, user_id: Optional[str] = None, guild_id: Optional[str] = None
    ) -> bool:
        if not user_id and not guild_id:
            return False

        await self._check_conn()
        async with self._lock:
            try:
                async with self.transaction():
                    if user_id:
                        async with self.conn.execute(
                            "DELETE FROM conversation_history WHERE user_id = ?", (user_id,)
                        ) as cursor:
                            affected = cursor.rowcount
                    elif guild_id:
                        async with self.conn.execute(
                            "DELETE FROM conversation_history WHERE guild_id = ?", (guild_id,)
                        ) as cursor:
                            affected = cursor.rowcount
                    return affected > 0
            except Exception as e:
                logger.error(f"Error clearing conversation history: {e}")
                return False

    async def check_reaction_permission(
        self, user_id, is_dm, guild_id, bot_message_id, reactor_id, channel_id=None
    ):
        await self._check_conn()
        if channel_id:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE channel_id=? AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (str(channel_id),)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND channel_id=? ORDER BY id DESC LIMIT 1"
            params2 = lambda row_id: (row_id, str(channel_id))
        elif is_dm:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE user_id=? AND guild_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (user_id,)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND user_id=? AND guild_id IS NULL ORDER BY id DESC LIMIT 1"
            params2 = lambda row_id: (row_id, user_id)
        else:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE guild_id=? AND user_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (guild_id,)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND guild_id=? AND user_id IS NULL ORDER BY id DESC LIMIT 1"
            params2 = lambda row_id: (row_id, guild_id)

        async with self._lock:
            async with self.conn.execute(sql1, params1) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if bot_message_id in ids or str(bot_message_id) in [str(x) for x in ids]:
                        if row["author_id"] and str(row["author_id"]) == str(reactor_id):
                            return True
                        async with self.conn.execute(sql2, params2(row["id"])) as prev_cur:
                            prev = await prev_cur.fetchone()
                            if (
                                prev
                                and prev["author_id"]
                                and str(prev["author_id"]) == str(reactor_id)
                            ):
                                return True
        return False

    async def get_context_for_message(self, user_id, is_dm, guild_id, message_id, channel_id=None):
        await self._check_conn()
        target_row = None
        if channel_id:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE channel_id=? AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (str(channel_id),)
            sql2 = "SELECT role, content, author_id FROM conversation_history WHERE id < ? AND channel_id=? ORDER BY id DESC LIMIT 10"
            params2 = lambda target_id: (target_id, str(channel_id))
        elif is_dm:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE user_id=? AND guild_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (user_id,)
            sql2 = "SELECT role, content, author_id FROM conversation_history WHERE id < ? AND user_id=? AND guild_id IS NULL ORDER BY id DESC LIMIT 10"
            params2 = lambda target_id: (target_id, user_id)
        else:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE guild_id=? AND user_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (guild_id,)
            sql2 = "SELECT role, content, author_id FROM conversation_history WHERE id < ? AND guild_id=? AND user_id IS NULL ORDER BY id DESC LIMIT 10"
            params2 = lambda target_id: (target_id, guild_id)

        async with self._lock:
            async with self.conn.execute(sql1, params1) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids or str(message_id) in [str(x) for x in ids]:
                        target_row = row
                        break

            if not target_row:
                return None, None

            async with self.conn.execute(sql2, params2(target_row["id"])) as cur:
                rows = await cur.fetchall()

        user_idx = None
        for i, r in enumerate(rows):
            if r["role"] == "user":
                if dict(target_row).get("author_id") and dict(r).get("author_id"):
                    if str(r["author_id"]) == str(target_row["author_id"]):
                        user_idx = i
                        break
                else:
                    user_idx = i
                    break

        if user_idx is None:
            return None, None

        prompt = rows[user_idx]["content"]
        context = [
            {"role": r["role"], "content": r["content"]} for r in reversed(rows[user_idx + 1 :])
        ]
        return prompt, context

    async def get_original_author_for_message(
        self, user_id, is_dm, guild_id, message_id, channel_id=None
    ) -> Optional[str]:
        """Resolve the original user author_id for a bot response message."""
        await self._check_conn()
        if channel_id:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE channel_id=? AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (str(channel_id),)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND channel_id=? AND role='user' ORDER BY id DESC LIMIT 1"
            params2 = lambda target_id: (target_id, str(channel_id))
        elif is_dm:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE user_id=? AND guild_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (user_id,)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND user_id=? AND guild_id IS NULL AND role='user' ORDER BY id DESC LIMIT 1"
            params2 = lambda target_id: (target_id, user_id)
        else:
            sql1 = "SELECT id, message_ids, author_id FROM conversation_history WHERE guild_id=? AND user_id IS NULL AND role='assistant' ORDER BY id DESC LIMIT 20"
            params1 = (guild_id,)
            sql2 = "SELECT author_id FROM conversation_history WHERE id < ? AND guild_id=? AND user_id IS NULL AND role='user' ORDER BY id DESC LIMIT 1"
            params2 = lambda target_id: (target_id, guild_id)

        async with self._lock:
            async with self.conn.execute(sql1, params1) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids or str(message_id) in [str(x) for x in ids]:
                        row_dict = dict(row)
                        if row_dict.get("author_id"):
                            return str(row_dict["author_id"])
                        async with self.conn.execute(sql2, params2(row["id"])) as prev_cur:
                            prev = await prev_cur.fetchone()
                            if prev and dict(prev).get("author_id"):
                                return str(dict(prev)["author_id"])
                        break
        return None

    async def get_unsummarized_messages(self, user_id, last_summary_time):
        await self._check_conn()
        if last_summary_time:
            sql = "SELECT role, content FROM conversation_history WHERE user_id=? AND timestamp > ? ORDER BY id ASC"
            params = (user_id, last_summary_time)
        else:
            sql = "SELECT role, content FROM conversation_history WHERE user_id=? ORDER BY id ASC"
            params = (user_id,)

        async with self._lock:
            async with self.conn.execute(sql, params) as cur:
                return [dict(row) for row in await cur.fetchall()]

    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation history statistics for the /safety dashboard"""
        await self._check_conn()
        stats = {}
        async with self._lock:
            async with self.conn.execute(
                "SELECT COUNT(*) as total FROM conversation_history"
            ) as cur:
                row = await cur.fetchone()
                stats["total_rows"] = row[0] if row else 0

            async with self.conn.execute("""
                SELECT guild_id, COUNT(*) as cnt FROM conversation_history 
                WHERE guild_id IS NOT NULL GROUP BY guild_id ORDER BY cnt DESC LIMIT 10
            """) as cur:
                stats["top_guilds"] = [(row[0], row[1]) async for row in cur]

            async with self.conn.execute("""
                SELECT user_id, COUNT(*) as cnt FROM conversation_history 
                WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY cnt DESC LIMIT 10
            """) as cur:
                stats["top_users"] = [(row[0], row[1]) async for row in cur]

        return stats

    async def get_guild_message_ids(self, guild_id: str) -> List[int]:
        """Fetch all bot message IDs for a specific guild"""
        await self._check_conn()
        all_ids = []
        async with self._lock:
            async with self.conn.execute(
                "SELECT message_ids FROM conversation_history WHERE guild_id = ? AND role = 'assistant'",
                (str(guild_id),),
            ) as cursor:
                async for row in cursor:
                    if row["message_ids"]:
                        try:
                            ids = json.loads(row["message_ids"])
                            if isinstance(ids, list):
                                all_ids.extend(ids)
                        except (json.JSONDecodeError, TypeError):
                            continue
        return list(set(int(mid) for mid in all_ids if mid))

    async def delete_user_data(self, user_id: str):
        """Wipe all data for a specific user ID across all tables."""
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                tables = [
                    "users",
                    "user_inventory",
                    "user_upgrades",
                    "user_currencies",
                    "user_params",
                    "user_personas",
                    "rare_hits",
                    "conversation_history",
                ]
                for table in tables:
                    async with self.conn.execute(
                        f"DELETE FROM {table} WHERE user_id = ?", (user_id,)
                    ):
                        pass
                logger.info(f"Wiped all data for user {user_id}")

    async def reset_all_user_data(self):
        """Wipe all user-related data (factory reset). DANGEROUS!"""
        await self._check_conn()
        async with self._lock:
            async with self.transaction():
                tables = [
                    "users",
                    "user_inventory",
                    "user_upgrades",
                    "user_currencies",
                    "user_params",
                    "user_personas",
                    "rare_hits",
                ]
                for table in tables:
                    async with self.conn.execute(f"DELETE FROM {table}"):
                        pass
                logger.info("FACTORY RESET: All user data wiped.")

    async def update_user_value(
        self, table: str, column: str, value: Any, user_id: Optional[str] = None
    ):
        """Update a specific column for one or all users."""
        await self._check_conn()
        async with self._lock:
            try:
                if user_id:
                    query = f"UPDATE {table} SET {column} = ? WHERE user_id = ?"
                    params = (value, user_id)
                else:
                    query = f"UPDATE {table} SET {column} = ?"
                    params = (value,)

                async with self.conn.execute(query, params):
                    await self._commit_if_not_in_tx()
                logger.info(
                    f"Updated {table}.{column} to {value} (Scope: {'Single' if user_id else 'Global'})"
                )
            except Exception as e:
                logger.error(f"Failed to update {table}.{column}: {e}")
                raise e

    async def get_general_stats(self) -> Dict[str, Any]:
        """Get general user statistics for the dashboard."""
        await self._check_conn()
        stats = {}
        async with self._lock:
            async with self.conn.execute("SELECT COUNT(*) FROM users") as cur:
                row = await cur.fetchone()
                stats["total_users"] = row[0] if row else 0

            async with self.conn.execute("SELECT COUNT(*) FROM user_inventory") as cur:
                row = await cur.fetchone()
                stats["total_inventory_items"] = row[0] if row else 0

            async with self.conn.execute(
                "SELECT SUM(amount) FROM user_currencies WHERE currency_type = 'clovers'"
            ) as cur:
                row = await cur.fetchone()
                stats["total_clovers"] = row[0] if row else 0

        return stats

    async def close(self):
        async with self._lock:
            if self.conn:
                await self.conn.close()
                self.conn = None


db = Database()
