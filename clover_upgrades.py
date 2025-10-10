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
    },
    "clover_gain": {
        "name": "☘ Clover Gain",
        "description": "Decreases how many rolls you need to gain a ☘ Clover by 1 per tier",
        "max_tier": 8,
        "requirements": {
            1: {"clovers": 10, "Lucky 🍀 (1 in 1,000)": 4},
            2: {"clovers": 25, "Lucky 🍀 (1 in 1,000)": 6, "Grass 🌱 (1 in 12,345)": 1},
            3: {"clovers": 75, "Lucky 🍀 (1 in 1,000)": 7, "Grass 🌱 (1 in 12,345)": 2},
            4: {"clovers": 150, "Prestigeous 💠 (1 in 124)": 25, "Crystallize 🔮 (1 in 1,248)": 12, "Grass 🌱 (1 in 12,345)": 3, "Otherworldly 🫧 (1 in 44,444)": 1},
            5: {"clovers": 250, "Redacted ⬛ (1 in 200,000)": 1}, # heh
            6: {"clovers": 400, "poop 💩 (1 in 123)": 40, "Money 💵 (1 in 888)": 15, "Lucky 🍀 (1 in 1,000)": 10},
            7: {"clovers": 600, "Jackpot 🤑 (1 in 777)": 77},
            8: {"clovers": 1000, "Uncommon 🟢 (1 in 4)": 150, "Emerald 🟢 (1 in 512)": 50, "Money 💵 (1 in 888)": 30, "Lucky 🍀 (1 in 1,000)": 20, "Archaic ❇️ (1 in 5,125)": 10, "Grass 🌱 (1 in 12,345)": 7, "Enigmatic 🧩 (1 in 40,404)": 4, "Planetary 🌍 (1 in 1,000,000)": 1}, # good luck bro (its also all greens)
        },
        "effect": lambda tier, user: {"clover_every": 10-tier}
    }
}
