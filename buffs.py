# Urch/buffs.py
import random
import time
from typing import Dict, Any, List, Tuple
from utils import currency_count, currency_remove, currency_add
from recipes import POTION_RECIPES
from raritylist import RARITIES


MAX_POTION_DURATION = 86400  # 24 hours max active duration
MAX_POTION_CHARGES = 1000

RARITY_ONE_IN_MAP: Dict[str, float] = {r[0]: (1.0 / r[1]) if r[1] > 0 else 0.0 for r in RARITIES}


async def apply_potion_craft(user_id: str, potion_id: str, amount: int = 1) -> bool:
    """Grants potion charges or updates expiration timestamp on craft with multi-craft support."""
    recipe = POTION_RECIPES.get(potion_id)
    if not recipe or amount < 1:
        return False

    buff = recipe["buff"]
    now = int(time.time())

    if buff["type"] == "charges":
        key = f"potion_charge_{potion_id}"
        current = await currency_count(user_id, key)
        new_charges = min(MAX_POTION_CHARGES, current + (buff["charges"] * amount))
        added = new_charges - current
        if added > 0:
            await currency_add(user_id, key, added)
    elif buff["type"] == "duration":
        key = f"potion_exp_{potion_id}"
        stored_exp = await currency_count(user_id, key)

        if 0 < stored_exp <= now:
            await currency_remove(user_id, key, stored_exp)
            stored_exp = 0

        base_exp = max(now, stored_exp)
        dur_to_add = buff["duration_seconds"] * amount
        new_exp = min(now + MAX_POTION_DURATION, base_exp + dur_to_add)

        if stored_exp > 0:
            await currency_remove(user_id, key, stored_exp)
        await currency_add(user_id, key, new_exp)

    return True


async def evaluate_active_buffs(user_id: str, context: str) -> Dict[str, Any]:
    """
    Evaluates all active potions for context ('manual' or 'autoroll').
    Deducts 1 charge for charge-based potions.
    Returns combined multipliers: luck_mult, clover_mult, extra_rolls, dupe_chance, dupe_min_one_in, active_names.
    """
    now = int(time.time())
    results = {
        "luck_mult": 1.0,
        "clover_mult": 1.0,
        "extra_rolls": 0,
        "dupe_chance": 0.0,
        "dupe_min_one_in": 1_000_000,
        "active_names": [],
    }

    for p_id, recipe in POTION_RECIPES.items():
        buff = recipe["buff"]
        if context not in buff["targets"]:
            continue

        is_active = False

        if buff["type"] == "charges":
            key = f"potion_charge_{p_id}"
            is_active = await currency_remove(user_id, key, 1)

        elif buff["type"] == "duration":
            key = f"potion_exp_{p_id}"
            exp_time = await currency_count(user_id, key)
            if exp_time > now + MAX_POTION_DURATION:
                # Clamp to max allowed duration rather than wiping out to 1 potion
                await currency_remove(user_id, key, exp_time)
                exp_time = now + MAX_POTION_DURATION
                await currency_add(user_id, key, exp_time)

            if exp_time > now:
                is_active = True
            elif exp_time > 0:
                await currency_remove(user_id, key, exp_time)

        if is_active:
            results["luck_mult"] *= buff.get("luck_mult", 1.0)
            results["clover_mult"] *= buff.get("clover_mult", 1.0)
            results["extra_rolls"] += buff.get("extra_rolls", 0)
            if "dupe_chance" in buff:
                results["dupe_chance"] = max(
                    results["dupe_chance"], float(buff.get("dupe_chance", 0.0))
                )
                results["dupe_min_one_in"] = min(
                    results["dupe_min_one_in"], float(buff.get("dupe_min_one_in", 1_000_000))
                )
            results["active_names"].append(recipe["name"])

    return results


def apply_dupe_buff(rolls: List[str], buff_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Applies active dupe_chance from buff_data to any rolled rarity at or above dupe_min_one_in.
    Returns (final_rolls_with_dupes, list_of_duped_rarities).
    """
    if not rolls or not buff_data:
        return list(rolls), []

    dupe_chance = float(buff_data.get("dupe_chance", 0.0))
    if dupe_chance <= 0.0:
        return list(rolls), []

    min_one_in = float(buff_data.get("dupe_min_one_in", 1_000_000))
    final_rolls: List[str] = []
    duped_rarities: List[str] = []

    for r in rolls:
        final_rolls.append(r)
        one_in = RARITY_ONE_IN_MAP.get(r, 0.0)
        if one_in + 1e-6 >= min_one_in:
            if random.random() < dupe_chance:
                final_rolls.append(r)
                duped_rarities.append(r)

    return final_rolls, duped_rarities


async def get_user_potion_summary(user_id: str, user_obj: Dict[str, Any] = None) -> List[str]:
    """
    Returns a list of formatted strings for active/held potions.
    e.g. ['x3 🧪 Small Luck Potion (5m 30s)', 'x1 😯 All or Nothing Potion']
    """
    now = int(time.time())
    potion_list = []

    for p_id, recipe in POTION_RECIPES.items():
        buff = recipe["buff"]
        if buff["type"] == "charges":
            key = f"potion_charge_{p_id}"
            charges = await currency_count(user_id, key, user_obj=user_obj)
            if charges > 0:
                base_charges = buff.get("charges", 1)
                if base_charges == 1:
                    potion_list.append(f"x{charges} {recipe['name']}")
                else:
                    if charges % base_charges == 0:
                        pot_count = charges // base_charges
                        potion_list.append(f"x{pot_count} {recipe['name']}")
                    else:
                        pot_count = max(1, (charges + base_charges - 1) // base_charges)
                        potion_list.append(f"x{pot_count} {recipe['name']} ({charges} rolls left)")
        elif buff["type"] == "duration":
            key = f"potion_exp_{p_id}"
            exp_time = await currency_count(user_id, key, user_obj=user_obj)
            if exp_time > now + 86400:
                exp_time = now + buff.get("duration_seconds", 300)

            if exp_time > now:
                rem_seconds = exp_time - now
                dur_per_pot = buff.get("duration_seconds", 1)
                pot_count = max(1, (rem_seconds + dur_per_pot - 1) // dur_per_pot)
                m, s = divmod(rem_seconds, 60)
                time_str = f"{m}m {s}s" if m > 0 else f"{s}s"
                potion_list.append(f"x{pot_count} {recipe['name']} ({time_str})")

    return potion_list
