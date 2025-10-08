# upgrades/luck_upgrades.py
import math
LUCK_UPGRADES = {
    "additive_luck": {
        "name": "🍀 Additive Luck",
        "description": "Gain +0.3 🍀 per tier \n Every 10th tier doubles the luck boost",
        "requirements": {
            1:  {"Common ⚪ (1 in 2)": 1},
            2:  {"Common ⚪ (1 in 2)": 2},
            3:  {"Uncommon 🟢 (1 in 4)": 1},
            4:  {"Uncommon 🟢 (1 in 4)": 2},
            5:  {"Good 👍 (1 in 8)": 1},
            6:  {"Good 👍 (1 in 8)": 2},
            7:  {"Rare 🔵 (1 in 16)": 1, "Common ⚪ (1 in 2)": 10},
            8:  {"Rare 🔵 (1 in 16)": 3, "Common ⚪ (1 in 2)": 5},
            9:  {"Cool 😎 (1 in 25)": 2},
            10: {"Cool 😎 (1 in 25)": 1, "Rare 🔵 (1 in 16)": 2, "Good 👍 (1 in 8)": 4, "Uncommon 🟢 (1 in 4)": 8}, # super buffed (atleast 1 in 25)
            11: {"Epic 🟣 (1 in 32)": 2},
            12: {"Hot ☀ (1 in 40)": 2, "Cool 😎 (1 in 25)": 4},
            13: {":53: (1 in 53)": 5},
            14: {"Great 🗣 (1 in 64)": 4, "Good 👍 (1 in 8)": 16},
            15: {"Man 👨 (1 in 100)": 2, "Great 🗣 (1 in 64)": 8, "Good 👍 (1 in 8)": 8},
            16: {"poop 💩 (1 in 123)": 3, "Nice 😂 (1 in 69)": 4},
            17: {"Gilded 💛 (1 in 128)": 5},
            18: {"Legendary 🏅 (1 in 256)": 2, "Epic 🟣 (1 in 32)": 4, "Rare 🔵 (1 in 16)": 8, "Uncommon 🟢 (1 in 4)": 16, "Common ⚪ (1 in 2)": 32},
            19: {"Pi 🥧 (1 in 314)": 3, "Hot ☀ (1 in 40)": 14},
            20: {"Ruby 🔶 (1 in 512)": 2, "ERROR ⚠ (1 in 404)": 4, "Nice 😂 (1 in 69)": 6, "Common ⚪ (1 in 2)": 25}, # super buffed (atleast 1 in 500)
            21: {"Ruby 🔶 (1 in 512)": 3, "Legendary 🏅 (1 in 256)": 1},
            22: {":53: [II] (1 in 530)": 3, ":53: (1 in 53)": 5},
            23: {"Anger 😡 (1 in 600)": 1, "Hot ☀ (1 in 40)": 6, "Cool 😎 (1 in 25)": 13},
            24: {"Freezing ❄️ (1 in 650)": 2, "Anger 😡 (1 in 600)": 2},
            25: {"Jackpot 🤑 (1 in 777)": 2, "Hell 🔥 (1 in 666)": 3, "Hot ☀ (1 in 40)": 10},
            26: {"Money 💵 (1 in 888)": 2, "Jackpot 🤑 (1 in 777)": 2, "Gilded 💛 (1 in 128)": 5},
            27: {"Ruby 🔶 (1 in 512)": 2, "Emerald 🟢 (1 in 512)": 2, "Sapphire 🔹 (1 in 512)": 2},
            28: {"Mythic ✨ (1 in 1,024)": 3, "Ruby 🔶 (1 in 512)": 1, "Emerald 🟢 (1 in 512)": 1, "Sapphire 🔹 (1 in 512)": 1},
            29: {"Mythic ✨ (1 in 1,024)": 4},
            30: {"Exceptional 😱 (1 in 1,500)": 2, "Mythic ✨ (1 in 1,024)": 1, "Lucky 🍀 (1 in 1,000)": 5}, # super buffed (1/1,000 range)
            31: {"Aureum 💎 (1 in 4,096)": 2}, # stuff beyond may be unbalanced because i didnt update them yet
            32: {"Unique 💖 (1 in 5,000)": 2},
            33: {":53: [III] (1 in 5,353)": 2},
            34: {"Very Nice 😏 (1 in 6,900)": 2},
            35: {"Ultimate  (1 in 8,192)": 2},
            36: {"Exode 🌠 (1 in 10,000)": 2},
            37: {"Unusual 🔎 (1 in 16,384)": 2},
            38: {"Godly 🤩 (1 in 21,500)": 2},
            39: {"Archidon 🌌 (1 in 22,500)": 2},
            40: {"Binary 💻 (1 in 32,768)": 2}, # super buffed (1/5,000 range)
            41: {":53: [IV] (1 in 53,530)": 2},
            42: {"Divine 🌃 (1 in 65,536)": 2},
            43: {"Ascendant 👼 (1 in 72,000)": 2},
            44: {"Miner ⛏ (1 in 90,100)": 2},
            45: {"Amazing 📜 (1 in 100,000)": 2},
            46: {"Easy 😃 (1 in 131,072)": 2},
            47: {"negus 🥶 (1 in 140,000)": 2},
            48: {"Redacted ⬛ (1 in 200,000)": 2},
            49: {"Skilled 🤸‍♂️ (1 in 262,144)": 2},
            50: {"Supreme 🪐 (1 in 350,000)": 2}, # super buffed
            51: {"Unstoppable ❌ (1 in 500,000)": 2},
            52: {"Slick 🤪 (1 in 524,288)": 2},
            53: {":53: [V] (1 in 530,530)": 2},
            54: {"Failure ⚠ (1 in 666,666)": 2},
            55: {"Lottery 🎰 (1 in 777,777)": 2},
            56: {"Space ☄ (1 in 999,999)": 2},
            57: {"Planetary 🌍 (1 in 1,000,000)": 2},
            58: {"Enlightened 🤔 (1 in 1,048,576)": 2},
            59: {"Interstellar 🌞 (1 in 1,300,000)": 2},
            60: {"Rainbow 🌈 (1 in 1,450,000)": 2} # super buffed
        },
        "effect": lambda tier, user: {"luck_bonus": (0.3 * (tier * (2**math.floor(tier/10))))},
    },
    "exp_luck": {
        "name": "📈 Exponential Luck",
        "description": "sqrt(log(rarity))^(🍀0.2*tier)",
        "max_tier": 5,
        "requirements": {
            1: {"Common ⚪ (1 in 2)": 24, "Uncommon 🟢 (1 in 4)": 16, "Rare 🔵 (1 in 16)": 12},
            2: {"Nice 😂 (1 in 69)": 10, "poop 💩 (1 in 123)": 10, "Legendary 🏅 (1 in 256)": 5},
            3: {"Gilded 💛 (1 in 128)": 8, "Ruby 🔶 (1 in 512)": 4},
            4: {"Epic 🟣 (1 in 32)": 27, "Anger 😡 (1 in 600)": 14, "Lucky 🍀 (1 in 1,000)": 6, "Exceptional 😱 (1 in 1,500)": 3},
            5: {"Aureum 💎 (1 in 4,096)": 8, ":53: [III] (1 in 5,353)": 5, "Ultimate  (1 in 8,192)": 3, "Godly 🤩 (1 in 21,500)": 1}
        },
        "effect": lambda tier, user: {
            "luck_bonus": ((tier or 0) ** 0.2) * 0.1
        },
    }
}
