# Urch/upgrades/autoroll_upgrades.py

AUTOROLL_UPGRADES = {
    "unlock": {
        "name": "Autoroll Engine",
        "description": "Unlocks the /autoroll command to roll automatically in the background.",
        "max_tier": 1,
        "cost": {
            "Amazing 📜 (1 in 100,000)": 1,
            "Steel 🔩 (1 in 123,456)": 1,
            "negus 🥶 (1 in 140,000)": 1
        },
        "effect": lambda tier, user: {"autoroll_unlocked": True} if tier >= 1 else {}
    }
}
