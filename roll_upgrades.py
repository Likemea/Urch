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
    "luck_roll": {
        "name": "🍀🎰 Lucky Rolls",
        "description": "+floor(log_10(Luck)*1.25) rolls",
        "max_tier": 1,
        "requirements": {
            1: {"Lucky 🍀 (1 in 1,000)": 100, "2048 🔢 (1 in 2,048)": 53, "Enigmatic 🧩 (1 in 40,404)": 10, "Unfathomable 🚰 (1 in 75,000)": 5, "Lottery 🎰 (1 in 777,777)": 1, "Rainbow 🌈 (1 in 1,450,000)": 1}
        },
        "effect": lambda tier, user: {"multi_roll: 0}, # CHANGE THIS LATER
    }
}
