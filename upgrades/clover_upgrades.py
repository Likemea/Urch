# Urch/upgrades/clover_upgrades.py

CLOVER_UPGRADES = {
    "clover_luck": {
        "name": "☘ Clover Luck",
        "description": "Increases 🍀Luck by 5% compounding per tier",
        "max_tier": 10,
        "requirements": {
            1: {"clovers": 1},
            2: {"clovers": 5},
            3: {"clovers": 20},
            4: {"clovers": 50},
            5: {"clovers": 125},
            6: {"clovers": 300},
            7: {"clovers": 800},
            8: {"clovers": 2000},
            9: {"clovers": 5000},
            10: {"clovers": 16384}
        },
        "effect": lambda tier, user: {"exp_bonus": 1.05**tier}
    },
    "clover_gain": {
        "name": "☘ Clover Gain",
        "description": "Decreases how many rolls you need to gain a ☘ Clover by 1 per tier",
        "max_tier": 8,
        "requirements": {
            1: {"clovers": 10, "lucky": 4},
            2: {"clovers": 25, "lucky": 6, "grass": 1},
            3: {"clovers": 75, "lucky": 7, "grass": 2},
            4: {"clovers": 150, "prestigeous": 25, "crystallize": 12, "grass": 3, "otherworldly": 1},
            5: {"clovers": 250, "redacted": 1}, # heh
            6: {"clovers": 400, "poop": 40, "money": 15, "lucky": 10},
            7: {"clovers": 600, "jackpot": 77},
            8: {"clovers": 1000, "uncommon": 150, "emerald": 50, "money": 30, "lucky": 20, "archaic": 10, "grass": 7, "enigmatic": 4, "planetary": 1}, # good luck bro (its also all greens)
        },
        "effect": lambda tier, user: {"clover_every": 10-tier}
    }
}