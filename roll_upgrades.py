# upgrades/roll_upgrades.py

ROLL_UPGRADES = {
    "multi_roll": {
        "name": "🎰 Multi Roll",
        "description": "+1 extra 🎰roll per tier",
        "max_tier": 3,
        "requirements": {
            1: {"Hot ☀ (1 in 40)": 8, "Pi 🥧 (1 in 314)": 4},
            2: {"Ruby 🔶 (1 in 512)": 5, "Mythic ✨ (1 in 1,024)": 4, "KROMER 💰 (1 in 1,997)": 2, "Unique 💖 (1 in 5,000)": 1},
            3: {"Good 👍 (1 in 8)": 50, "Very Nice 😏 (1 in 6,900)": 4, "Ultimate  (1 in 8,192)": 3, "Exode 🌠 (1 in 10,000)": 2, "Godly 🤩 (1 in 21,500)": 1}
        },
        "effect": lambda tier, user: {"multi_roll": tier},
    }
}
