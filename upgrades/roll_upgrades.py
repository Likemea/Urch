# Urch/upgrades/roll_upgrades.py

ROLL_UPGRADES = {
    "multi_roll": {
        "name": "🎰 Multi Roll",
        "description": "+1 extra 🎰roll per tier",
        "max_tier": 3,
        "requirements": {
            1: {"hot": 8, "pi": 4},
            2: {"ruby": 5, "mythic": 4, "kromer": 2, "unique": 1},
            3: {"good": 50, "very_nice": 4, "ultimate": 3, "exode": 2, "godly": 1}
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
    }
}
