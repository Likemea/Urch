# Urch/upgrades/roll_upgrades.py

ROLL_UPGRADES = {
    "multi_roll": {
        "name": "🎰 Multi Roll",
        "description": "+1 extra 🎰roll per tier",
        "max_tier": 5,
        "requirements": {
            1: {"hot": 8, "pi": 4},
            2: {"ruby": 5, "mythic": 4, "kromer": 2, "unique": 1},
            3: {"good": 50, "very_nice": 4, "ultimate": 3, "exode": 2, "godly": 1},
            4: {"mythic": 65, "unique": 30, "extreme": 14, "superman": 6, "archidon": 4, "continental": 3, "enigmatic": 2},
            5: {"archaic": 76, "extreme": 53, "exotic": 27, "godly": 15, "continental": 11, "otherworldly": 8, "53_4": 6, "ascendant": 5, "negus": 3, "skilled": 2, "unstoppable": 1}
        },
        "effect": lambda tier, user: {"multi_roll": tier},
    },
    "lucky_roll": {
        "name": "🍀🎰 Lucky Rolls",
        "description": "Gain extra rolls based on your Luck!\nEffect: +floor(log10(Luck)*1.25) rolls",
        "max_tier": 1,
        "requirements": {
             1: {"lucky": 100, "2048": 53, "enigmatic": 10, "unfathomable": 5, "lottery": 1, "rainbow": 1}
        },
        "effect": lambda tier, user: {"lucky_roll": tier == 1}, 
    },
    "autoroll_unlock": {
        "name": "⚙️🎰 Autoroll",
        "description": "Unlocks the /autoroll command",
        "max_tier": 1,
        "requirements": {
            1: {
                "kromer": 97,
                "archaic": 76,
                "exode": 48,
                "binary": 24,
                "amazing": 12,
                "steel": 10,
                "negus": 7,
                "planetary": 4,
                "matrix": 2,
            }
        },
        "effect": lambda tier, user: {"autoroll_unlocked": True} if tier >= 1 else {}
    }
}
