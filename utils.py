# Urch/utils.py
import json
import os
import random
from typing import Dict, List, Optional, Tuple
import asyncio
from database import db
from datetime import datetime
from database import DB_PATH
from upgrades import get_upgrade_effect as calc_upgrade_effect # Import logic
from raritylist import RARITIES

# Map IDs to Full Names
RARITY_ID_TO_NAME = {r[2]: r[0] for r in RARITIES}
# Set of Full Names for fast checking
RARITY_NAME_SET = {r[0] for r in RARITIES}

def resolve_item_key(key: str) -> Tuple[str, str]:
    """
    Determines if a key is a Rarity (Inventory) or Currency.
    Returns (db_key, category_type).
    category_type is 'inventory' or 'currency'.
    """
    # 1. Is it a Rarity ID? (e.g., "common") -> Map to Full Name
    if key in RARITY_ID_TO_NAME:
        return RARITY_ID_TO_NAME[key], "inventory"
    
    # 2. Is it already a Full Rarity Name? (e.g., "Common ⚪...") -> Use as is
    if key in RARITY_NAME_SET:
        return key, "inventory"
        
    # 3. Otherwise, assume it's a Currency (e.g., "clovers")
    return key, "currency"

# Constants
LUCK_GROWTH_PER_ROLL = 0.01
CHECKLIST_BONUS = 0.03
DM_HISTORY_LIMIT = 10
SERVER_HISTORY_LIMIT = 10

# Model list
MODEL_LIST = {
    "1": {"id": "llama-3.1-8b-instant", "disp": "⚡ Fast"},
    "2": {"id": "openai/gpt-oss-20b", "disp": "⚡🧠 Thinking (Fast)"},
    "3": {"id": "openai/gpt-oss-120b", "disp": "🧠 Thinking"},    
    "4": {"id": "moonshotai/kimi-k2-instruct-0905", "disp": "🎭 Creative"},
    "5": {"id": "llama-3.3-70b-versatile", "disp": "🔘 All-rounder"},
    "6": {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "disp": "⚡👁 Vision (Fast)"},
    "7": {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "disp": "👁 Vision"}
}

DEFAULT_AI_PARAMS = {
    "max_completion_tokens": 500,
    "temperature": 0.75,
    "top_p": 1,
    "model": "Auto",
    "reasoning": "Auto",
    "user_persona": "",
    "ai_persona": "",
    "memory_enabled": True,
    "memory_frequency": 10,
    "memory_probability": 0.5
}

# --- User Data Functions ---

async def ensure_user(user_id: str) -> Dict[str, any]:
    """Ensure user exists and return their data"""
    await db.ensure_user(user_id)
    return await db.get_user_data(user_id) or {}

async def get_user_data(user_id: str) -> Dict[str, any]:
    """Get user data (for direct access - use ensure_user for creation)"""
    return await db.get_user_data(user_id) or {}

async def save_user_data(user_id: str, data: Dict[str, any]):
    await db.ensure_user(user_id)
    return await db.save_user_data(user_id, data)
    
async def update_user_data(user_id: str, new_rarity: str, action: str = "none"):
    await db.ensure_user(user_id)
    user = await db.get_user_data(user_id)
    if not user: return

    # Rarity check
    if new_rarity not in RARITY_NAME_SET:
        pass # Should theoretically be in set if coming from roll_rarity

    # Highscore Logic
    rarity_names = [r[0] for r in RARITIES]
    current_high = user.get('highscore')
    update_high = False
    
    if not current_high:
        update_high = True
    elif new_rarity in rarity_names:
        try:
            if rarity_names.index(new_rarity) > rarity_names.index(current_high):
                update_high = True
        except ValueError:
            pass
            
    if update_high:
        user['highscore'] = new_rarity

    if action == "keep":
        # Add to inventory (Rarity)
        inventory = user.setdefault("inventory", {})
        inventory[new_rarity] = inventory.get(new_rarity, 0) + 1
        
        # Mark Discovered
        discovered = user.setdefault("discovered", {})
        discovered[new_rarity] = True
        
        # Stats
        user['roll_count'] = user.get('roll_count', 0) + 1
        
        # Luck Growth
        current_luck = user.get('luck_multi', 1.0)
        new_luck = current_luck + LUCK_GROWTH_PER_ROLL
        user['luck_multi'] = round(new_luck, 3)
        
        if new_luck > user.get('max_luck', 1.0):
            user['max_luck'] = round(new_luck, 3)
            
        # Clover Logic
        bonuses = await get_upgrade_effect(user_id, user_obj=user)
        effective_luck = (new_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]
        
        if effective_luck >= 1000:
             every = bonuses.get("clover_every", 10)
             current_rolls = user['roll_count']
             
             expected = int((current_rolls // every) * user.get('clover_multi', 1.0))
             already = user.get('clovers_earned', 0)
             
             if expected > already:
                 diff = expected - already
                 # Add Clovers (Currency)
                 currencies = user.setdefault("currencies", {})
                 currencies["clovers"] = currencies.get("clovers", 0) + diff
                 user['clovers_earned'] = expected

    await db.save_user_data(user_id, user)

# ───────────────────────────────
# INVENTORY & CURRENCY SYSTEM
# ───────────────────────────────

async def currency_add(user_id: str, item_key: str, amount: int = 1):
    """Smart add: detects if item is currency or inventory based on key"""
    user = await ensure_user(user_id)
    
    db_key, category = resolve_item_key(item_key)
    
    if category == "currency":
        curr = user.setdefault("currencies", {})
        curr[db_key] = curr.get(db_key, 0) + int(amount)
    else:
        # Inventory Item
        inv = user.setdefault("inventory", {})
        inv[db_key] = inv.get(db_key, 0) + int(amount)
        # Auto-discover if adding an item
        disc = user.setdefault("discovered", {})
        disc[db_key] = True
        
    await db.save_user_data(user_id, user)

async def currency_remove(user_id: str, item_key: str, amount: int = 1) -> bool:
    """Smart remove: checks correct storage location"""
    user = await ensure_user(user_id)
    db_key, category = resolve_item_key(item_key)
    
    if category == "currency":
        currencies = user.get("currencies", {})
        if currencies.get(db_key, 0) >= amount:
            currencies[db_key] -= amount
            if currencies[db_key] == 0: del currencies[db_key]
            await db.save_user_data(user_id, user)
            return True
        return False
    else:
        # Inventory
        inventory = user.get("inventory", {})
        if inventory.get(db_key, 0) >= amount:
            inventory[db_key] -= amount
            if inventory[db_key] == 0: del inventory[db_key]
            await db.save_user_data(user_id, user)
            return True
        return False

async def currency_count(user_id: str, item_key: str) -> int:
    """Smart count: looks in correct storage location"""
    user = await get_user_data(user_id)
    if not user: return 0
    
    db_key, category = resolve_item_key(item_key)
    
    if category == "currency":
        return int(user.get("currencies", {}).get(db_key, 0))
    else:
        return int(user.get("inventory", {}).get(db_key, 0))

async def has_requirements(user_id: str, requirements: Dict[str, int]) -> Tuple[bool, Dict[str, int]]:
    """Checks requirements supporting both IDs, Full Names, and Currencies"""
    user = await ensure_user(user_id)
    missing = {}
    
    for item_key, need in requirements.items():
        db_key, category = resolve_item_key(item_key)
        
        have = 0
        if category == "currency":
            have = user.get("currencies", {}).get(db_key, 0)
        else:
            have = user.get("inventory", {}).get(db_key, 0)
            
        if have < need:
            missing[db_key] = need - have # Return DB key (Full Name) for display clarity
            
    return (len(missing) == 0, missing)

async def consume_requirements(user_id: str, requirements: Dict[str, int]) -> bool:
    """Consumes items from both currencies and inventory"""
    ok, missing = await has_requirements(user_id, requirements)
    if not ok: return False
    
    user = await ensure_user(user_id)
    
    for item_key, need in requirements.items():
        db_key, category = resolve_item_key(item_key)
        
        if category == "currency":
            # Direct modify dict ref
            if "currencies" not in user: user["currencies"] = {}
            user["currencies"][db_key] -= need
        else:
            if "inventory" not in user: user["inventory"] = {}
            user["inventory"][db_key] -= need
            
    await db.save_user_data(user_id, user)
    return True

async def get_item_count(user_id: str, item_key: str) -> int:
    """Wrapper for currency_count to maintain compatibility"""
    return await currency_count(user_id, item_key)

async def inventory_all_items_sorted(user_id: str, rarities_list: list) -> list:
    """
    Returns sorted inventory items. 
    rarities_list: List of tuples (Name, Prob, ID) from RARITIES
    """
    user = await get_user_data(user_id)
    if not user: return []
    inv = user.get("inventory", {})
    
    # Sort by index in the master RARITIES list
    # rarities_list[i][0] is the Full Name
    order = {r[0]: idx for idx, r in enumerate(rarities_list)}
    
    # Only sort items that are actually in the Rarity list (excludes random junk)
    # If you want to include others at the end, use .get(k, 9999)
    sorted_items = sorted(
        [(k, v) for k, v in inv.items() if k in order],
        key=lambda kv: order.get(kv[0], 9999), 
        reverse=True
    )
    return sorted_items
    
async def roll_rarity(user_id: str) -> str:
    user = await ensure_user(user_id)
    
    if 'luck_override' in user and user['luck_override']:
        luck = float(user['luck_override'])
    else:
        base_luck = float(user.get("luck_multi", 1.0))
        bonuses = await get_upgrade_effect(str(user_id), user_obj=user)
        luck = (base_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]

    luck = max(1.0, luck)
    
    # Unpack for weighted choice
    rarity_names = [r[0] for r in RARITIES]
    base_probs = [r[1] for r in RARITIES]
    total_base = sum(base_probs)
    
    adjusted_weights = []
    total_rarities = len(rarity_names)

    for idx, prob in enumerate(base_probs):
        p = prob / total_base
        rarity_rank = idx / max(1, total_rarities - 1)
        
        if luck <= 1.0:
            weight = p
        else:
            # Power curve for luck
            weight = p * (luck ** (rarity_rank * 1.2))
            
        adjusted_weights.append(weight)

    return random.choices(rarity_names, weights=adjusted_weights, k=1)[0]

# --- Upgrade Functions ---

async def get_upgrade_effect(user_id: str, user_obj: dict = None) -> Dict[str, float]:
    if user_obj is None:
        user_obj = await get_user_data(user_id)
        
    return calc_upgrade_effect(user_id, user_obj)

async def get_checklist_bonus(user_id: str) -> Dict[str, float]:
    user = await ensure_user(user_id) 
    discovered = user.get("discovered", {}) or {}
    count = sum(1 for v in discovered.values() if v)
    multiplier = 1.0 + (CHECKLIST_BONUS * count)
    return {"exp_bonus": multiplier, "discovered_count": count}

# --- AI Parameters Functions ---

async def get_user_ai_params(user_id: str) -> Dict[str, any]:
    await db.ensure_user_params(user_id)
    params = await db.get_user_params(user_id)
    
    for k, v in DEFAULT_AI_PARAMS.items():
        if k not in params:
            params[k] = v
    
    return params

async def set_user_ai_param(user_id: str, param_name: str, value: any):
    await db.ensure_user_params(user_id)
    await db.set_user_param(user_id, param_name, value)

# --- Memory Functions ---

async def get_last_summary_time(user_id: str) -> Optional[str]:
    params = await db.get_user_params(user_id)
    return params.get("last_summary_time")

async def update_last_summary_time(user_id: str):
    import datetime
    await set_user_ai_param(user_id, "last_summary_time", datetime.datetime.now().isoformat())

async def get_unsummarized_messages(user_id: str) -> List[Dict[str, str]]:
    last_time = await get_last_summary_time(user_id)
    return await db.get_unsummarized_messages(user_id, last_time)

# --- Persona Functions ---

async def get_user_personas(user_id: str) -> Tuple[Dict[str, Dict[str, str]], str]:
    return await db.get_user_personas(user_id)

async def add_new_persona(user_id: str, name: str, user_p: str, ai_p: str) -> Tuple[bool, str]:
    personas, _ = await db.get_user_personas(user_id)
    if len(personas) >= 10:
        return False, "Max 10 personas allowed."
    if name in personas:
        return False, "Persona name already exists."
    
    success = await db.add_persona(user_id, name, user_p, ai_p)
    return success, "Success" if success else "Failed to add persona"

async def delete_user_persona(user_id: str, name: str) -> bool:
    return await db.delete_persona(user_id, name)

async def equip_user_persona(user_id: str, name: str) -> bool:
    return await db.equip_persona(user_id, name)

async def edit_existing_persona(user_id: str, name: str, user_p: str, ai_p: str) -> bool:
    return await db.edit_persona(user_id, name, user_p, ai_p)

async def save_conversation_history(): pass
async def load_conversation_history(): pass
async def get_messages_for_context(user_id, is_dm, guild_id=None, include_internal=False, read_only=True):
    return await db.get_messages_for_context(user_id if is_dm else None, guild_id if not is_dm else None, 
                                           DM_HISTORY_LIMIT if is_dm else SERVER_HISTORY_LIMIT, include_internal, read_only)

async def append_message_for_context(user_id, is_dm, role, content, guild_id=None, message_ids=None, author_id=None):
    await db.append_message(user_id if is_dm else None, guild_id if not is_dm else None, role, content, message_ids, str(author_id) if author_id else None)

async def update_message_in_history(user_id, is_dm, guild_id, message_id, new_content):
    return await db.update_message_in_history(user_id, guild_id, message_id, new_content)

async def delete_message_from_history(user_id, is_dm, guild_id, message_id):
    return await db.delete_message_from_history(user_id, guild_id, message_id)

async def check_reaction_permission(user_id, is_dm, guild_id, bot_msg_id, reactor_id):
    return await db.check_reaction_permission(user_id, guild_id, bot_msg_id, reactor_id)

async def get_context_for_message(user_id, is_dm, guild_id, message_id):
    return await db.get_context_for_message(user_id, guild_id, message_id)

# Export database instance
__all__ = [
    'db', 'MODEL_LIST', 'DEFAULT_AI_PARAMS', 'LUCK_GROWTH_PER_ROLL', 'CHECKLIST_BONUS',
    'ensure_user', 'get_user_data', 'save_user_data', 'create_backup',
    'currency_add', 'currency_remove', 'currency_count', 'has_requirements',
    'consume_requirements', 'inventory_all_items_sorted', 'get_upgrade_effect',
    'get_checklist_bonus', 'get_user_ai_params', 'set_user_ai_param',
    'get_last_summary_time', 'update_last_summary_time', 'get_unsummarized_messages',
    'get_user_personas', 'add_new_persona', 'delete_user_persona',
    'equip_user_persona', 'edit_existing_persona', 'load_conversation_history',
    'save_conversation_history', 'get_messages_for_context', 'append_message_for_context',
    'update_message_in_history', 'delete_message_from_history', 'check_reaction_permission',
    'get_context_for_message'
]