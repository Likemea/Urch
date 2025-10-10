# upgrades/clover_upgrades.py

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
    }
}
