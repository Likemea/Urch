# Urch/upgrades/clover_upgrades.py

CLOVER_UPGRADES = {
    "clover_luck": {
        "name": "☘ Clover Luck",
        "description": "Increases 🍀Luck by 5% compounding per tier",
        "max_tier": 12,
        "requirements": {
            1: {"clovers": 1},
            2: {"clovers": 5},
            3: {"clovers": 20, "good": 50, "nice": 20, "lucky": 4},
            4: {"clovers": 50},
            5: {"clovers": 125},
            6: {"clovers": 300, "poop": 42, "jackpot": 30, "money": 20, "lucky": 15, "insane": 7, "unique": 3},
            7: {"clovers": 500, "lucky": 23, "ultimate": 3, "grass": 1},
            8: {"clovers": 800, "rare": 128, "epic": 100, "great": 78, "man": 50, "error": 9, "53_2": 5},
            9: {"clovers": 1200, "emerald": 52, "lucky": 36, "very_nice": 16, "ultimate": 8, "exotic": 5, "archidon": 2},
            10: {"clovers": 1800, "crystallize": 96, "aureum": 64, "grass": 32, "quantum": 24, "divine": 18, "redacted": 11, "supreme": 8, "slick": 5, "53_5": 3, "lottery": 1},
            11: {"clovers": 2650, "hell": 150, "lucky": 120, "triangle": 90, "very_nice": 81, "extreme": 74, "exode": 60, "godly": 35, "enigmatic": 22, "53_4": 16, "unfathomable": 10, "amazing": 5},
            12: {"clovers": 3333, "otherworldly": 33, "easy": 20, "redacted": 15, "supreme": 10, "slick": 5, "53_5": 5, "deletion": 3, "acceleration": 2, "atmospheric": 1}
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