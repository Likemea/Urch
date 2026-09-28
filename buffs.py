# Urch/buffs.py
import time
from typing import Dict, Any, List
from utils import currency_count, currency_remove, currency_add
from recipes import POTION_RECIPES


async def apply_potion_craft(user_id: str, potion_id: str, amount: int = 1) -> bool:
    """Grants potion charges or updates expiration timestamp on craft with multi-craft support."""
    recipe = POTION_RECIPES.get(potion_id)
    if not recipe or amount < 1:
        return False

    buff = recipe["buff"]
    now = int(time.time())

    if buff["type"] == "charges":
        key = f"potion_charge_{potion_id}"
        await currency_add(user_id, key, buff["charges"] * amount)
    elif buff["type"] == "duration":
        key = f"potion_exp_{potion_id}"
        stored_exp = await currency_count(user_id, key)

        if stored_exp > now + 86400 or (0 < stored_exp <= now):
            await currency_remove(user_id, key, stored_exp)
            stored_exp = 0

        base_exp = max(now, stored_exp)
        new_exp = base_exp + (buff["duration_seconds"] * amount)

        if stored_exp > 0:
            await currency_remove(user_id, key, stored_exp)
        await currency_add(user_id, key, new_exp)

    return True


async def evaluate_active_buffs(user_id: str, context: str) -> Dict[str, Any]:
    """
    Evaluates all active potions for context ('manual' or 'autoroll').
    Deducts 1 charge for charge-based potions.
    Returns combined multipliers: luck_mult, clover_mult, extra_rolls, active_names.
    """
    now = int(time.time())
    results = {"luck_mult": 1.0, "clover_mult": 1.0, "extra_rolls": 0, "active_names": []}

    for p_id, recipe in POTION_RECIPES.items():
        buff = recipe["buff"]
        if context not in buff["targets"]:
            continue

        is_active = False

        if buff["type"] == "charges":
            key = f"potion_charge_{p_id}"
            count = await currency_count(user_id, key)
            if count > 0:
                is_active = True
                await currency_remove(user_id, key, 1)

        elif buff["type"] == "duration":
            key = f"potion_exp_{p_id}"
            exp_time = await currency_count(user_id, key)
            if exp_time > now + 86400:
                await currency_remove(user_id, key, exp_time)
                exp_time = now + buff.get("duration_seconds", 300)
                await currency_add(user_id, key, exp_time)

            if exp_time > now:
                is_active = True
            elif exp_time > 0:
                await currency_remove(user_id, key, exp_time)

        if is_active:
            results["luck_mult"] *= buff.get("luck_mult", 1.0)
            results["clover_mult"] *= buff.get("clover_mult", 1.0)
            results["extra_rolls"] += buff.get("extra_rolls", 0)
            results["active_names"].append(recipe["name"])

    return results


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
