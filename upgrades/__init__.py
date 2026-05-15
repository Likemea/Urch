# Urch/upgrades/__init__.py
import math
from typing import Dict

from .luck_upgrades import LUCK_UPGRADES
from .roll_upgrades import ROLL_UPGRADES
from .clover_upgrades import CLOVER_UPGRADES

UPGRADE_CATEGORIES = {
    "luck": LUCK_UPGRADES,
    "roll": ROLL_UPGRADES,
    "clover": CLOVER_UPGRADES,
}

# 1. Update arguments to accept user_obj and the pre-calculated checklist bonus
def get_upgrade_effect(user_id: str, user_obj: dict = None, checklist_exp_bonus: float = 1.0) -> Dict[str, float]:
    """
    Returns combined upgrade-derived modifiers for a user.
    Pure logic only - does not fetch from DB.
    """
    # 2. REMOVED the import from utils to fix ImportError
    # from utils import user_data, get_checklist_bonus <-- DELETED
    from raritylist import RARITIES

    effects = {
        "luck_bonus": 0.0,
        "exp_bonus": 1.0,
        "multi_roll": 0,   
        "clover_bonus": 0.0,
        "clover_every": 10,
        "lucky_roll_active": False,
        "autoroll_unlocked": False,
    }

    # 3. Use the passed object directly
    user = user_obj
    if not user:
        return effects    
        
    # 4. Apply the passed checklist bonus
    effects["exp_bonus"] *= checklist_exp_bonus

    # Upgrades are expected in user["upgrades"] as categories:
    upgrades = user.get("upgrades", {})

    # ---- Luck category ----
    luck_upgs = upgrades.get("luck", {})
    for key, tier in luck_upgs.items():
        if not tier: continue
        tier = int(tier)
        
        if key in LUCK_UPGRADES:
            defn = LUCK_UPGRADES[key]
            
            # Simple per-tier additive bonus
            if "effect_per_tier" in defn:
                effects["luck_bonus"] += defn["effect_per_tier"] * tier
                
            # Complex callback effect
            elif "effect" in defn and callable(defn["effect"]):
                try:
                    res = defn["effect"](tier, user)
                    if isinstance(res, dict):
                        effects["luck_bonus"] += res.get("luck_bonus", 0.0)
                        if "exp_bonus" in res:
                            effects["exp_bonus"] *= res["exp_bonus"]
                        effects["multi_roll"] += res.get("multi_roll", 0)
                        effects["clover_bonus"] += res.get("clover_bonus", 0.0)
                except Exception as e:
                    print(f"Error calculating luck upgrade {key}: {e}")

        # exponential luck
        if key == "exp_luck" and key in LUCK_UPGRADES:
            rarity_names = [r[0] for r in RARITIES]
            best = user.get("highscore", rarity_names[0] if rarity_names else None)
            try:
                idx = rarity_names.index(best)
            except Exception:
                idx = 0
            exponent = 0.2 * tier
            try:
                base = max(0.0, math.log(idx + 2))
                multiplier = base ** exponent if base > 0 else 1.0
            except Exception:
                multiplier = 1.0
            effects["exp_bonus"] *= multiplier

    # ---- Roll category ----
    roll_upgs = upgrades.get("roll", {})
    for key, tier in roll_upgs.items():
        if not tier: continue
        tier = int(tier)
        if key in ROLL_UPGRADES:
            defn = ROLL_UPGRADES[key]
            if key == "multi_roll":
                if "effect" in defn and callable(defn["effect"]):
                    res = defn["effect"](tier, user)
                    effects["multi_roll"] += int(res.get("multi_roll", 0))
                else:
                    effects["multi_roll"] += tier
            elif key == "lucky_roll":
                 if "effect" in defn and callable(defn["effect"]):
                    res = defn["effect"](tier, user)
                    if res.get("lucky_roll"):
                        effects["lucky_roll_active"] = True
            elif key == "autoroll_unlock":
                if "effect" in defn and callable(defn["effect"]):
                    res = defn["effect"](tier, user)
                    if res.get("autoroll_unlocked"):
                        effects["autoroll_unlocked"] = True
                    
    # ---- Clover category ----
    clover_upgs = upgrades.get("clover", {})
    for key, tier in clover_upgs.items():
        if not tier: continue
        tier = int(tier)
        if key in CLOVER_UPGRADES:
            defn = CLOVER_UPGRADES[key]
            if "effect" in defn and callable(defn["effect"]):
                res = defn["effect"](tier, user)
                if isinstance(res, dict):
                    effects["luck_bonus"] += res.get("luck_bonus", 0.0)
                    effects["exp_bonus"] *= res.get("exp_bonus", 1.0)
                    effects["multi_roll"] += res.get("multi_roll", 0)
                    effects["clover_bonus"] += res.get("clover_bonus", 0.0)
                    if "clover_every" in res:
                        effects["clover_every"] = res["clover_every"]
                        
    if effects["lucky_roll_active"]:
        base_luck = float(user.get("luck_multi", 1.0))
        current_luck = (base_luck + effects["luck_bonus"]) * effects["exp_bonus"]
        
        if current_luck > 1:
            try:
                extra_rolls = math.floor(math.log10(current_luck) * 1.25)
                effects["multi_roll"] += int(extra_rolls)
            except ValueError:
                pass

    return effects