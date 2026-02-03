# Urch/database.py
import aiosqlite
import asyncio
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import contextlib

logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._lock = asyncio.Lock()
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._lock_usage: Dict[str, datetime] = {}
        
    async def initialize(self):
        """Initialize database and create tables"""
        self.conn = await aiosqlite.connect(self.db_path)
        # Enable WAL mode for concurrency and speed
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = aiosqlite.Row
        # Users table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                roll_count INTEGER DEFAULT 0,
                highscore TEXT,
                luck_multi REAL DEFAULT 1.0,
                max_luck REAL DEFAULT 1.0,
                clover_multi REAL DEFAULT 1.0,
                clover_every INTEGER DEFAULT 10,
                clovers_earned INTEGER DEFAULT 0,
                luck_override REAL
            )
        """)
        
        # User inventory table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                discovered BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        
        # User upgrades table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_upgrades (
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                upgrade_key TEXT NOT NULL,
                tier INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, category, upgrade_key)
            )
        """)
        
        # User currencies table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_currencies (
                user_id TEXT NOT NULL,
                currency_type TEXT NOT NULL,
                amount INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, currency_type)
            )
        """)
        
        # User parameters table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_params (
                user_id TEXT PRIMARY KEY,
                max_completion_tokens INTEGER DEFAULT 500,
                temperature REAL DEFAULT 0.75,
                top_p REAL DEFAULT 1.0,
                model TEXT DEFAULT 'Auto',
                reasoning TEXT DEFAULT 'Auto',
                memory_enabled BOOLEAN DEFAULT TRUE,
                memory_frequency INTEGER DEFAULT 10,
                memory_probability REAL DEFAULT 0.35,
                user_persona TEXT DEFAULT '',
                ai_persona TEXT DEFAULT '',
                active_persona TEXT DEFAULT 'Default',
                last_summary_time TEXT
            )
        """)
        
        # User personas table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_personas (
                user_id TEXT NOT NULL,
                persona_name TEXT NOT NULL,
                user_persona TEXT DEFAULT '',
                ai_persona TEXT DEFAULT '',
                PRIMARY KEY (user_id, persona_name)
            )
        """)
        
        # Conversation history table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message_ids TEXT,
                author_id TEXT
            )
        """)
        
        # Create indexes for performance
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_user_time 
            ON conversation_history (user_id, timestamp)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_guild_time 
            ON conversation_history (guild_id, timestamp)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_user 
            ON user_inventory (user_id, item_name)
        """)
        
        await self.conn.commit()
        
        logger.info("Database initialized successfully")
        
    @contextlib.asynccontextmanager
    async def lock_user(self, user_id: str):
        """Asynchronous context manager for per-user locking"""
        async with self._lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = asyncio.Lock()
            lock = self._user_locks[user_id]
            self._lock_usage[user_id] = datetime.now()
        
        async with lock:
            yield
            
        # Optional: Periodic cleanup
        if len(self._user_locks) > 100:
            asyncio.create_task(self._cleanup_locks())

    async def _cleanup_locks(self):
        """Internal: Clean up old locks that haven't been used in a while"""
        async with self._lock:
            now = datetime.now()
            threshold = now - timedelta(hours=1)
            to_delete = [
                uid for uid, last_used in self._lock_usage.items() 
                if last_used < threshold and not self._user_locks[uid].locked()
            ]
            for uid in to_delete:
                del self._user_locks[uid]
                del self._lock_usage[uid]

    async def _check_conn(self):
        if not self.conn:
            await self.initialize()
    
    # --- User Data ---
    
    async def ensure_user(self, user_id: str) -> bool:
        await self._check_conn()
        async with self._lock:
            cursor = await self.conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await self.conn.commit()
            return cursor.rowcount > 0
    
    async def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        await self._check_conn()
        # No lock needed for reads usually, but safe to keep if unsure about concurrent writes
        async with self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_row = await cursor.fetchone()
            if not user_row: return None
            user_data = dict(user_row)
            
        async with self.conn.execute("SELECT item_name, quantity, discovered FROM user_inventory WHERE user_id = ?", (user_id,)) as cursor:
            inventory = {}
            discovered = {}
            async for row in cursor:
                inventory[row["item_name"]] = row["quantity"]
                discovered[row["item_name"]] = bool(row["discovered"])
            user_data["inventory"] = inventory
            user_data["discovered"] = discovered
            
        async with self.conn.execute("SELECT category, upgrade_key, tier FROM user_upgrades WHERE user_id = ?", (user_id,)) as cursor:
            upgrades = {"luck": {}, "roll": {}, "clover": {}}
            async for row in cursor:
                if row["category"] not in upgrades: upgrades[row["category"]] = {}
                upgrades[row["category"]][row["upgrade_key"]] = row["tier"]
            user_data["upgrades"] = upgrades
            
        async with self.conn.execute("SELECT currency_type, amount FROM user_currencies WHERE user_id = ?", (user_id,)) as cursor:
            currencies = {}
            async for row in cursor:
                currencies[row["currency_type"]] = row["amount"]
            user_data["currencies"] = currencies
            
        return user_data
    
    async def save_user_data(self, user_id: str, data: Dict[str, Any]):
        await self._check_conn()
        async with self._lock:
            try:
                await self.conn.execute("BEGIN TRANSACTION")
                await self.conn.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, roll_count, highscore, luck_multi, max_luck, clover_multi, 
                        clover_every, clovers_earned, luck_override)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, data.get("roll_count", 0), data.get("highscore"), data.get("luck_multi", 1.0),
                    data.get("max_luck", 1.0), data.get("clover_multi", 1.0), data.get("clover_every", 10),
                    data.get("clovers_earned", 0), data.get("luck_override")
                ))
                
                if "inventory" in data:
                    for item_name, quantity in data["inventory"].items():
                        disc = data.get("discovered", {}).get(item_name, False)
                        await self.conn.execute("INSERT OR REPLACE INTO user_inventory (user_id, item_name, quantity, discovered) VALUES (?, ?, ?, ?)", 
                                        (user_id, item_name, quantity, disc))
                
                if "upgrades" in data:
                    for category, upgrades in data["upgrades"].items():
                        for upgrade_key, tier in upgrades.items():
                            await self.conn.execute("INSERT OR REPLACE INTO user_upgrades (user_id, category, upgrade_key, tier) VALUES (?, ?, ?, ?)", 
                                            (user_id, category, upgrade_key, tier))
                
                if "currencies" in data:
                    for currency_type, amount in data["currencies"].items():
                        await self.conn.execute("INSERT OR REPLACE INTO user_currencies (user_id, currency_type, amount) VALUES (?, ?, ?)", 
                                        (user_id, currency_type, amount))
                
                await self.conn.commit()
            except Exception as e:
                await self.conn.rollback()
                raise e
    
    # --- User Parameters ---
    
    async def ensure_user_params(self, user_id: str):
        await self._check_conn()
        async with self._lock:
            await self.conn.execute("INSERT OR IGNORE INTO user_params (user_id) VALUES (?)", (user_id,))
            await self.conn.commit()

    async def get_user_params(self, user_id: str) -> Dict[str, Any]:
        await self._check_conn()
        async with self.conn.execute("SELECT * FROM user_params WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else self._get_default_params()

    def _get_default_params(self) -> Dict[str, Any]:
        return {"max_completion_tokens": 500, "temperature": 0.75, "top_p": 1.0, "model": "Auto", "reasoning": "Auto", "memory_enabled": True, "memory_frequency": 10, "memory_probability": 0.35, "user_persona": "", "ai_persona": "", "active_persona": "Default", "last_summary_time": None}

    async def set_user_params(self, user_id: str, params: Dict[str, Any]):
        """Set user parameters"""
        await self._check_conn()
        async with self._lock:
            await self.conn.execute("""
                INSERT OR REPLACE INTO user_params 
                (user_id, max_completion_tokens, temperature, top_p, model, reasoning,
                 memory_enabled, memory_frequency, memory_probability, user_persona,
                 ai_persona, active_persona, last_summary_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                params.get("max_completion_tokens", 500),
                params.get("temperature", 0.75),
                params.get("top_p", 1.0),
                params.get("model", "Auto"),
                params.get("reasoning", "Auto"),
                params.get("memory_enabled", True),
                params.get("memory_frequency", 10),
                params.get("memory_probability", 0.35),
                params.get("user_persona", ""),
                params.get("ai_persona", ""),
                params.get("active_persona", "Default"),
                params.get("last_summary_time")
            ))
            await self.conn.commit()
    
    async def set_user_param(self, user_id: str, param_name: str, value: Any):
        await self._check_conn()
        async with self._lock:
            await self.conn.execute(f"UPDATE user_params SET {param_name} = ? WHERE user_id = ?", (value, user_id))
            await self.conn.commit()

    async def get_user_personas(self, user_id: str) -> Tuple[Dict[str, Dict[str, str]], str]:
        await self._check_conn()
        async with self.conn.execute("SELECT active_persona FROM user_params WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            active = row["active_persona"] if row else "Default"
        
        personas = {}
        async with self.conn.execute("SELECT * FROM user_personas WHERE user_id = ?", (user_id,)) as cur:
            async for row in cur:
                personas[row["persona_name"]] = {"user_persona": row["user_persona"], "ai_persona": row["ai_persona"]}
        
        if "Default" not in personas:
            personas["Default"] = {"user_persona": "", "ai_persona": ""}
            await self.add_persona(user_id, "Default", "", "")
        return personas, active

    async def add_persona(self, user_id: str, name: str, user_p: str, ai_p: str) -> bool:
        await self._check_conn()
        async with self._lock:
            try:
                await self.conn.execute("INSERT INTO user_personas (user_id, persona_name, user_persona, ai_persona) VALUES (?, ?, ?, ?)", (user_id, name, user_p, ai_p))
                await self.conn.commit()
                return True
            except aiosqlite.IntegrityError: return False
    
    async def delete_persona(self, user_id: str, name: str) -> bool:
        """Delete a persona"""
        await self._check_conn()
        async with self._lock:
            await self.conn.execute("BEGIN TRANSACTION")
            try:
                # Check if it's the last persona
                async with self.conn.execute(
                    "SELECT COUNT(*) as count FROM user_personas WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row["count"] <= 1:
                        return False
                
                # Delete the persona
                await self.conn.execute(
                    "DELETE FROM user_personas WHERE user_id = ? AND persona_name = ?",
                    (user_id, name)
                )
                
                # If it was active, set Default as active
                async with self.conn.execute(
                    "SELECT active_persona FROM user_params WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row["active_persona"] == name:
                        await self.conn.execute(
                            "UPDATE user_params SET active_persona = ? WHERE user_id = ?",
                            ("Default", user_id)
                        )
                
                await self.conn.commit()
                return True
            except Exception as e:
                await self.conn.rollback()
                raise e
    
    async def equip_persona(self, user_id: str, name: str) -> bool:
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute("SELECT user_persona, ai_persona FROM user_personas WHERE user_id=? AND persona_name=?", (user_id, name)) as cur:
                row = await cur.fetchone()
                if not row: return False
                await self.conn.execute("UPDATE user_params SET active_persona=?, user_persona=?, ai_persona=? WHERE user_id=?", (name, row[0], row[1], user_id))
                await self.conn.commit()
                return True

    async def edit_persona(self, user_id: str, name: str, user_p: str, ai_p: str) -> bool:
        await self._check_conn()
        async with self._lock:
            await self.conn.execute("UPDATE user_personas SET user_persona=?, ai_persona=? WHERE user_id=? AND persona_name=?", (user_p, ai_p, user_id, name))
            # Also update if it is the currently active one
            await self.conn.execute("""
                UPDATE user_params SET user_persona=?, ai_persona=? 
                WHERE user_id=? AND active_persona=?
            """, (user_p, ai_p, user_id, name))
            await self.conn.commit()
            return True
    
    # --- Conversation History ---

    async def add_conversation_message(self, user_id: str, guild_id: str, role: str, content: str, message_ids: list = None, author_id: str = None):
        await self._check_conn()
        timestamp = datetime.utcnow().isoformat()
        
        msg_ids_json = json.dumps(message_ids) if message_ids else None
        
        async with self._lock:
            await self.conn.execute("""
                INSERT INTO conversation_history 
                (user_id, guild_id, role, content, timestamp, message_ids, author_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, guild_id, role, content, timestamp, msg_ids_json, author_id))
            await self.conn.commit()
    
    async def append_message(self, user_id, guild_id, role, content, message_ids=None, author_id=None):
        await self._check_conn()
        async with self._lock:
            await self.conn.execute("""
                INSERT INTO conversation_history (user_id, guild_id, role, content, timestamp, message_ids, author_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, guild_id, role, content, datetime.now().isoformat(), json.dumps(message_ids) if message_ids else None, author_id))
            await self.conn.commit()

    async def get_messages_for_context(self, user_id=None, guild_id=None, limit=10, include_internal=False, read_only=True):
        await self._check_conn()
        if user_id and guild_id:
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
        
        async with self.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            msgs = []
            for row in reversed(rows): # Chronological
                m = {"role": row["role"], "content": row["content"]}
                if include_internal:
                    m.update({"id": row["id"], "timestamp": row["timestamp"], "message_ids": json.loads(row["message_ids"] or "[]"), "author_id": row["author_id"]})
                msgs.append(m)
            return msgs

    async def update_message_in_history(self, user_id, guild_id, message_id, new_content):
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute("SELECT id, message_ids FROM conversation_history WHERE user_id=? OR guild_id=? ORDER BY id DESC LIMIT 50", (user_id, guild_id)) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids:
                        await self.conn.execute("UPDATE conversation_history SET content=? WHERE id=?", (new_content, row["id"]))
                        await self.conn.commit()
                        return True
        return False

    async def delete_message_from_history(self, user_id, guild_id, message_id):
        await self._check_conn()
        async with self._lock:
            async with self.conn.execute("SELECT id, message_ids FROM conversation_history WHERE user_id=? OR guild_id=? ORDER BY id DESC LIMIT 50", (user_id, guild_id)) as cur:
                async for row in cur:
                    ids = json.loads(row["message_ids"] or "[]")
                    if message_id in ids:
                        await self.conn.execute("DELETE FROM conversation_history WHERE id=?", (row["id"],))
                        await self.conn.commit()
                        return True
        return False
            
    async def clear_conversation_history(self, user_id: Optional[str] = None, guild_id: Optional[str] = None) -> bool:
        if not user_id and not guild_id:
            return False
            
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    if user_id:
                        cursor = await db.execute("DELETE FROM conversation_history WHERE user_id = ?", (user_id,))
                    elif guild_id:
                        cursor = await db.execute("DELETE FROM conversation_history WHERE guild_id = ?", (guild_id,))
                    
                    affected = cursor.rowcount
                    await db.commit()
                    return affected > 0
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Error clearing conversation history: {e}")
                    return False
        
    async def check_reaction_permission(self, user_id, guild_id, bot_message_id, reactor_id):
        await self._check_conn()
        async with self.conn.execute("SELECT id, message_ids FROM conversation_history WHERE (user_id=? OR guild_id=?) AND role='assistant' ORDER BY id DESC LIMIT 20", (user_id, guild_id)) as cur:
            async for row in cur:
                ids = json.loads(row["message_ids"] or "[]")
                if bot_message_id in ids:
                    async with self.conn.execute("SELECT author_id FROM conversation_history WHERE id < ? AND (user_id=? OR guild_id=?) ORDER BY id DESC LIMIT 1", (row["id"], user_id, guild_id)) as prev_cur:
                        prev = await prev_cur.fetchone()
                        if prev and prev["author_id"] == str(reactor_id):
                            return True
        return False

    async def get_context_for_message(self, user_id, guild_id, message_id):
        await self._check_conn()
        target_row = None
        async with self.conn.execute("SELECT id, message_ids FROM conversation_history WHERE (user_id=? OR guild_id=?) AND role='assistant' ORDER BY id DESC LIMIT 20", (user_id, guild_id)) as cur:
            async for row in cur:
                ids = json.loads(row["message_ids"] or "[]")
                if message_id in ids:
                    target_row = row
                    break
        
        if not target_row: return None, None

        async with self.conn.execute("SELECT role, content FROM conversation_history WHERE id < ? AND (user_id=? OR guild_id=?) ORDER BY id DESC LIMIT 10", (target_row["id"], user_id, guild_id)) as cur:
            rows = await cur.fetchall()
            
        if not rows: return None, None
            
        prompt = rows[0]["content"]
        context = [{"role": r["role"], "content": r["content"]} for r in reversed(rows[1:])]
        return prompt, context

    async def get_unsummarized_messages(self, user_id, last_summary_time):
        await self._check_conn()
        if last_summary_time:
            sql = "SELECT role, content FROM conversation_history WHERE user_id=? AND timestamp > ? ORDER BY id ASC"
            params = (user_id, last_summary_time)
        else:
            sql = "SELECT role, content FROM conversation_history WHERE user_id=? ORDER BY id ASC"
            params = (user_id,)
        
        async with self.conn.execute(sql, params) as cur:
            return [dict(row) for row in await cur.fetchall()]
        
    async def close(self):
        if self.conn:
            await self.conn.close()

db = Database()