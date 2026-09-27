# Urch/utils.py
import json
import os
import random
from typing import Dict, List, Optional, Tuple, Union
from collections import Counter
import asyncio
from database import db
from datetime import datetime
from database import DB_PATH
from upgrades import get_upgrade_effect as calc_upgrade_effect
from raritylist import RARITIES
import discord
from providers import MODELS as MODEL_LIST

LOG_GUILD_ID = 1444003568263630900
LOG_CHANNEL_NAME = "✨🎰・rare-rolls"

RARITY_ID_TO_NAME = {r[2]: r[0] for r in RARITIES}
RARITY_NAME_SET = {r[0] for r in RARITIES}
RARITY_NAMES = [r[0] for r in RARITIES]
RARITY_BASE_PROBS = [r[1] for r in RARITIES]
TOTAL_BASE_PROB = sum(RARITY_BASE_PROBS)
TOTAL_RARITIES = len(RARITIES)
RARITY_RANKS = [idx / max(1, TOTAL_RARITIES - 1) for idx in range(TOTAL_RARITIES)]
RARITY_INDEX_MAP = {r[0]: idx for idx, r in enumerate(RARITIES)}

def resolve_item_key(key: str) -> Tuple[str, str]:
    """
    determines if a key is a rarity or currency
    returns (db_key, category_type)
    category_type is 'inventory' or 'currency'
    """
    if key in RARITY_ID_TO_NAME:
        return RARITY_ID_TO_NAME[key], "inventory"
    
    if key in RARITY_NAME_SET:
        return key, "inventory"
        
    return key, "currency"

LUCK_GROWTH_PER_ROLL = 0.01
CHECKLIST_BONUS = 0.03
DM_HISTORY_LIMIT = 16
SERVER_HISTORY_LIMIT = 16

DEFAULT_AI_PARAMS = {
    "max_completion_tokens": 1000,
    "temperature": 0.75,
    "top_p": 1,
    "model": "Auto", 
    "reasoning": "none",
    "tooling": "Auto",
    "user_persona": "",
    "ai_persona": ""
}

# --- User Data Functions ---

async def ensure_user(user_id: str) -> Dict[str, any]:
    """ensure user exists and return their data"""
    await db.ensure_user(user_id)
    return await db.get_user_data(user_id) or {}

async def get_user_data(user_id: str) -> Dict[str, any]:
    """get user data (for direct access - use ensure_user for creation)"""
    return await db.get_user_data(user_id) or {}

async def save_user_data(user_id: str, data: Dict[str, any]):
    await db.ensure_user(user_id)
    return await db.save_user_data(user_id, data)
    
async def update_user_data(user_id: str, new_rarity: Union[str, List[str]], action: str = "none") -> Optional[Dict[str, any]]:
    async with db.lock_user(user_id):
        user = await db.get_user_data(user_id)
        if not user: return None

        if isinstance(new_rarity, str):
            rarities_list = [new_rarity]
        else:
            rarities_list = list(new_rarity)

        if not rarities_list:
            return user

        current_high = user.get('highscore')
        current_high_idx = RARITY_INDEX_MAP.get(current_high, -1) if current_high else -1
        highest_idx = current_high_idx
        best_rarity = current_high

        for r in rarities_list:
            idx = RARITY_INDEX_MAP.get(r, -1)
            if idx > highest_idx:
                highest_idx = idx
                best_rarity = r

        if best_rarity and best_rarity != current_high:
            user['highscore'] = best_rarity

        if action == "keep":
            inventory = user.setdefault("inventory", {})
            discovered = user.setdefault("discovered", {})

            rarity_counts = Counter(rarities_list)
            for r, count in rarity_counts.items():
                inventory[r] = inventory.get(r, 0) + count
                discovered[r] = True

            roll_count_inc = len(rarities_list)
            user['roll_count'] = user.get('roll_count', 0) + roll_count_inc

            current_luck = user.get('luck_multi', 1.0)
            new_luck = current_luck + (LUCK_GROWTH_PER_ROLL * roll_count_inc)
            user['luck_multi'] = round(new_luck, 3)

            if new_luck > user.get('max_luck', 1.0):
                user['max_luck'] = round(new_luck, 3)

            bonuses = await get_upgrade_effect(user_id, user_obj=user)
            effective_luck = (new_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]

            if effective_luck >= 1000:
                 every = bonuses.get("clover_every", 10)
                 current_rolls = user['roll_count']

                 expected = int((current_rolls // every) * user.get('clover_multi', 1.0))
                 already = user.get('clovers_earned', 0)

                 if expected > already:
                     diff = expected - already
                     currencies = user.setdefault("currencies", {})
                     currencies["clovers"] = currencies.get("clovers", 0) + diff
                     user['clovers_earned'] = expected

        await db.save_user_data(user_id, user)
        return user

# ───────────────────────────────
# INVENTORY & CURRENCY SYSTEM
# ───────────────────────────────

async def currency_add(user_id: str, item_key: str, amount: int = 1):
    """detects if item is currency or inventory based on key"""
    async with db.lock_user(user_id):
        user = await db.get_user_data(user_id)
        if not user: return
        
        db_key, category = resolve_item_key(item_key)
        
        if category == "currency":
            curr = user.setdefault("currencies", {})
            curr[db_key] = curr.get(db_key, 0) + int(amount)
        else:
            inv = user.setdefault("inventory", {})
            inv[db_key] = inv.get(db_key, 0) + int(amount)
            disc = user.setdefault("discovered", {})
            disc[db_key] = True
            
        await db.save_user_data(user_id, user)

async def currency_remove(user_id: str, item_key: str, amount: int = 1) -> bool:
    """checks correct storage location"""
    async with db.lock_user(user_id):
        user = await db.get_user_data(user_id)
        if not user: return False
        
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

async def currency_count(user_id: str, item_key: str, user_obj: Dict[str, any] = None) -> int:
    """looks in correct storage location"""
    user = user_obj if user_obj is not None else await get_user_data(user_id)
    if not user: return 0
    
    db_key, category = resolve_item_key(item_key)
    
    if category == "currency":
        return int(user.get("currencies", {}).get(db_key, 0))
    else:
        return int(user.get("inventory", {}).get(db_key, 0))

async def has_requirements(user_id: str, requirements: Dict[str, int], user_obj: Dict[str, any] = None) -> Tuple[bool, Dict[str, int]]:
    """Checks requirements both IDs, Full Names, and Currencies"""
    user = user_obj if user_obj is not None else await ensure_user(user_id)
    missing = {}
    
    for item_key, need in requirements.items():
        db_key, category = resolve_item_key(item_key)
        
        have = 0
        if category == "currency":
            have = user.get("currencies", {}).get(db_key, 0)
        else:
            have = user.get("inventory", {}).get(db_key, 0)
            
        if have < need:
            missing[db_key] = need - have
            
    return (len(missing) == 0, missing)

async def consume_requirements(user_id: str, requirements: Dict[str, int]) -> bool:
    async with db.lock_user(user_id):
        ok, missing = await has_requirements(user_id, requirements)
        if not ok: return False
        
        user = await db.get_user_data(user_id)
        if not user: return False
        
        for item_key, need in requirements.items():
            db_key, category = resolve_item_key(item_key)
            
            if category == "currency":
                if "currencies" not in user: user["currencies"] = {}
                user["currencies"][db_key] -= need
            else:
                if "inventory" not in user: user["inventory"] = {}
                user["inventory"][db_key] -= need
                
        await db.save_user_data(user_id, user)
        return True

async def get_item_count(user_id: str, item_key: str, user_obj: Dict[str, any] = None) -> int:
    """Wrapper for currency_count"""
    return await currency_count(user_id, item_key, user_obj=user_obj)

async def inventory_all_items_sorted(user_id: str, rarities_list: list) -> list:
    """
    Returns sorted inventory items. 
    rarities_list: List of tuples (Name, Prob, ID) from RARITIES
    """
    user = await get_user_data(user_id)
    if not user: return []
    inv = user.get("inventory", {})
    
    order = {r[0]: idx for idx, r in enumerate(rarities_list)}
    
    sorted_items = sorted(
        [(k, v) for k, v in inv.items() if k in order],
        key=lambda kv: order.get(kv[0], 9999), 
        reverse=True
    )
    return sorted_items
    
async def roll_rarities(user_id: str, count: int = 1, provided_luck: float = None) -> List[str]:
    if count <= 0:
        return []
    if provided_luck is not None:
        luck = provided_luck
    else:
        user = await ensure_user(user_id)
        if 'luck_override' in user and user['luck_override']:
            luck = float(user['luck_override'])
        else:
            base_luck = float(user.get("luck_multi", 1.0))
            bonuses = await get_upgrade_effect(str(user_id), user_obj=user)
            luck = (base_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]

    luck = max(1.0, float(luck or 1.0))

    if luck <= 1.0:
        weights = RARITY_BASE_PROBS
    else:
        weights = [
            p * (luck ** (rank * 1.2))
            for p, rank in zip(RARITY_BASE_PROBS, RARITY_RANKS)
        ]

    return random.choices(RARITY_NAMES, weights=weights, k=count)

async def roll_rarity(user_id: str, provided_luck: float = None) -> str:
    res = await roll_rarities(user_id, count=1, provided_luck=provided_luck)
    return res[0] if res else RARITY_NAMES[0]

async def process_autorolls(user_ids: List[str]):
    """Process one tick of autorolls for all active users"""
    if not user_ids:
        return []

    from buffs import evaluate_active_buffs

    updates = []
    rare_hits = [] # List of (user_id, rarity_name, one_in, total_luck)

    for user_id in user_ids:
        user = await db.get_user_data(user_id)
        if not user: continue

        # Luck and bonuses
        bonuses = await get_upgrade_effect(user_id, user_obj=user)
        luck_override = user.get('luck_override')
        if luck_override is not None:
            total_luck = float(luck_override)
        else:
            base_luck = float(user.get("luck_multi", 1.0))
            total_luck = (base_luck + bonuses["luck_bonus"]) * bonuses["exp_bonus"]
        
        buff_data = await evaluate_active_buffs(user_id, context="autoroll")
        total_luck *= buff_data["luck_mult"]

        total_luck = max(1.0, total_luck)
        
        extra_rolls = bonuses.get("multi_roll", 0)
        num_rolls = max(1, 1 + int(extra_rolls / 2))
        
        results = await roll_rarities(user_id, count=num_rolls, provided_luck=total_luck)
        
        roll_count_inc = len(results)
        new_highscore = user.get("highscore")
        rarity_order = [r[0] for r in RARITIES]
        
        inventory_diff = {}
        
        for res in results:
            inventory_diff[res] = inventory_diff.get(res, 0) + 1
            
            if not new_highscore or rarity_order.index(res) > rarity_order.index(new_highscore):
                new_highscore = res
            
            # if one_in >= (total_luck * 100), it's a rare roll
            rarity_data = next((r for r in RARITIES if r[0] == res), None)
            if rarity_data:
                weight = rarity_data[1]
                total_weight = sum(r[1] for r in RARITIES)
                one_in = total_weight / weight
                
                if one_in >= (total_luck * 100):
                    rare_hits.append((user_id, res, one_in, total_luck))

        # Luck growth
        current_luck = user.get('luck_multi', 1.0)
        new_luck = round(current_luck + (LUCK_GROWTH_PER_ROLL * roll_count_inc), 3)
        max_luck = max(user.get('max_luck', 1.0), new_luck)
        
        # Clovers
        clovers_earned = user.get('clovers_earned', 0)
        currency_diff = {}
        if total_luck >= 1000:
            every = bonuses.get("clover_every", 10)
            total_rolls_after = user.get('roll_count', 0) + roll_count_inc
            expected = int((total_rolls_after // every) * user.get('clover_multi', 1.0) * buff_data["clover_mult"])
            if expected > clovers_earned:
                diff = expected - clovers_earned
                currency_diff["clovers"] = diff
                clovers_earned = expected

        updates.append({
            "user_id": user_id,
            "roll_count": user.get('roll_count', 0) + roll_count_inc,
            "highscore": new_highscore,
            "luck_multi": new_luck,
            "max_luck": max_luck,
            "clovers_earned": clovers_earned,
            "inventory_diff": inventory_diff,
            "currency_diff": currency_diff
        })

    if updates:
        await db.bulk_update_autoroll(updates)
    
    return rare_hits

async def log_rare_roll(bot, user, rarity_name, one_in, total_luck):
    try:
        guild = bot.get_guild(LOG_GUILD_ID)
        if not guild: return
        channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        if not channel: return
            
        if one_in >= (total_luck * 5000):
            title_prefix = "♾ *OMNIVERSAL MILESTONE!!!*"
            color = discord.Color.dark_theme()
        elif one_in >= (total_luck * 2500):
            title_prefix = "💠 *MULTIVERSAL MILESTONE!!*"
            color = discord.Color.purple()
        elif one_in >= (total_luck * 1000):
            title_prefix = "🪐 *UNIVERSAL MILESTONE!*"
            color = discord.Color.dark_purple()
        elif one_in >= (total_luck * 500):
            title_prefix = "🌌 Galactic Milestone!!!"
            color = discord.Color.dark_blue()
        elif one_in >= (total_luck * 250):
            title_prefix = "🌟 Stellar Milestone!!"
            color = discord.Color.blue()
        elif one_in >= (total_luck * 100):
            title_prefix = "🌍 Planetary Milestone!"
            color = discord.Color.green()
        else:
            title_prefix = "🚨 Rare Roll!"
            color = discord.Color.gold()

        embed = discord.Embed(
            title=f"{title_prefix}",
            description=f"**{user.name}** just rolled **{rarity_name}**!",
            color=color
        )
        embed.add_field(name="Luck", value=format_number(total_luck), inline=True)
        embed.add_field(name="Rarity", value=f"1 in {one_in:,.0f}", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()

        webhooks = await channel.webhooks()
        webhook = discord.utils.get(webhooks, name="Rarity Logger")
        if not webhook:
            webhook = await channel.create_webhook(name="Rarity Logger")
            
        await webhook.send(embed=embed, username="Rarity Logger", avatar_url=bot.user.display_avatar.url)
        
    except Exception as e:
        print(f"Failed to log rare roll: {e}")

# --- Upgrade Functions ---

async def get_upgrade_effect(user_id: str, user_obj: dict = None) -> Dict[str, float]:
    if user_obj is None:
        user_obj = await get_user_data(user_id)
    
    if not user_obj:
        return calc_upgrade_effect(user_id, {}, 1.0)

    discovered = user_obj.get("discovered", {}) or {}
    count = sum(1 for v in discovered.values() if v)
    checklist_multiplier = 1.0 + (CHECKLIST_BONUS * count)

    return calc_upgrade_effect(user_id, user_obj, checklist_multiplier)

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

# --- Summary Functions ---

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

async def get_messages_for_context(user_id, is_dm, guild_id=None, include_internal=False, read_only=True):
    return await db.get_messages_for_context(user_id if is_dm else None, guild_id if not is_dm else None, 
                                           DM_HISTORY_LIMIT if is_dm else SERVER_HISTORY_LIMIT, include_internal, read_only)

async def append_message_for_context(user_id, is_dm, role, content, guild_id=None, message_ids=None, author_id=None): 
    db_user_id = str(user_id) if is_dm else None
    db_guild_id = str(guild_id) if not is_dm and guild_id else None
    final_author_id = str(author_id) if author_id else None

    await db.add_conversation_message(
        user_id=db_user_id,
        guild_id=db_guild_id,
        role=role,
        content=content,
        message_ids=message_ids,
        author_id=final_author_id
    )

async def update_message_in_history(user_id, is_dm, guild_id, message_id, new_content):
    return await db.update_message_in_history(user_id, guild_id, message_id, new_content)

async def delete_message_from_history(user_id, is_dm, guild_id, message_id):
    return await db.delete_message_from_history(user_id, guild_id, message_id)

async def check_reaction_permission(user_id, is_dm, guild_id, bot_msg_id, reactor_id):
    return await db.check_reaction_permission(user_id, guild_id, bot_msg_id, reactor_id)

async def get_context_for_message(user_id, is_dm, guild_id, message_id):
    return await db.get_context_for_message(user_id, guild_id, message_id)

def format_number(num: float) -> str:
    if num < 1000:
        return f"{num:.2f}"
    
    suffixes = ["", "k", "M", "B", "T", "Qa", "Qn", "Sx", "Sp", "Oc", "No", "Dc"]
    magnitude = 0
    while round(abs(num), 2) >= 1000 and magnitude < len(suffixes) - 1:
        magnitude += 1
        num /= 1000.0
    
    return f"{num:.2f}{suffixes[magnitude]}"

__all__ = [
    'db', 'MODEL_LIST', 'DEFAULT_AI_PARAMS', 'LUCK_GROWTH_PER_ROLL', 'CHECKLIST_BONUS',
    'ensure_user', 'get_user_data', 'save_user_data',
    'currency_add', 'currency_remove', 'currency_count', 'has_requirements',
    'consume_requirements', 'inventory_all_items_sorted', 'get_upgrade_effect',
    'get_checklist_bonus', 'get_user_ai_params', 'set_user_ai_param',
    'get_last_summary_time', 'update_last_summary_time', 'get_unsummarized_messages',
    'get_user_personas', 'add_new_persona', 'delete_user_persona',
    'equip_user_persona', 'edit_existing_persona', 'get_messages_for_context',
    'append_message_for_context', 'update_message_in_history', 'delete_message_from_history',
    'check_reaction_permission', 'get_context_for_message', 'format_number',
    'process_autorolls', 'log_rare_roll', 'roll_rarity', 'roll_rarities', 'update_user_data'
]