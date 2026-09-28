# Urch/recipes.py

POTION_RECIPES = {
    "small_luck_potion": {
        "name": "🧪 Small Luck Potion",
        "description": "+25% Luck for 2 minutes",
        "reqs": {
            "lucky": 10,
        },
        "buff": {
            "type": "duration",
            "duration_seconds": 120,
            "targets": ["manual"],
            "luck_mult": 1.25,
        },
    },
    "medium_luck_potion": {
        "name": "🧪 Medium Luck Potion",
        "description": "+50% Luck for 3 minutes",
        "reqs": {
            "lucky": 35,
            "rare": 64,
        },
        "buff": {
            "type": "duration",
            "duration_seconds": 300,
            "targets": ["manual"],
            "luck_mult": 1.5,
        },
    },
    "large_luck_potion": {
        "name": "🧪 Large Luck Potion",
        "description": "+100% Luck for 5 minutes",
        "reqs": {"lucky": 100, "ruby": 70, "money": 50},
        "buff": {
            "type": "duration",
            "duration_seconds": 360,
            "targets": ["manual"],
            "luck_mult": 2.0,
        },
    },
    "hypercharge_potion": {
        "name": "⚡ Hypercharge Potion",
        "description": "+500% Luck & +1 Extra Roll for the next 25 manual rolls.",
        "reqs": {
            "clovers": 2500,
            "jackpot": 100,
            "ruby": 250,
            "crystallize": 50,
            "ultimate": 20,
            "archidon": 8,
        },
        "buff": {
            "type": "charges",
            "charges": 50,
            "targets": ["manual"],
            "luck_mult": 6.0,
            "clover_mult": 1.0,
            "extra_rolls": 1,
        },
    },
    "overclock_potion": {
        "name": "🌀 Overclock Potion",
        "description": "+200% Luck and 2x Clovers to ALL rolls for 10 minutes.",
        "reqs": {"clovers": 5000, "lucky": 500, "aureum": 50, "otherworldly": 5},
        "buff": {
            "type": "duration",
            "duration_seconds": 600,
            "targets": ["manual", "autoroll"],
            "luck_mult": 3.0,
            "clover_mult": 2.0,
            "extra_rolls": 0,
        },
    },
    "all_or_nothing_potion": {
        "name": "😯 All or Nothing Potion",
        "description": "+1000% Luck for the next manual roll!",
        "reqs": {"clovers": 1000, "jackpot": 777, "lucky": 650, "unique": 475, "amazing": 100},
        "buff": {
            "type": "charges",
            "charges": 1,
            "targets": ["manual"],
            "luck_mult": 11.0,
        },
    },
}
