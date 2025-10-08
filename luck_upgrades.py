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
            10: {"Cool 😎 (1 in 25)": 2, "Rare 🔵 (1 in 16)": 4, "Good 👍 (1 in 8)": 8, "Uncommon 🟢 (1 in 4)": 16}, # super buffed (atleast 1 in 25)
            11: {"Epic 🟣 (1 in 32)": 4},
            12: {"Hot ☀ (1 in 40)": 2, "Cool 😎 (1 in 25)": 4},
            13: {":53: (1 in 53)": 5},
            14: {"Great 🗣 (1 in 64)": 4, "Good 👍 (1 in 8)": 16},
            15: {"Man 👨 (1 in 100)": 2, "Great 🗣 (1 in 64)": 4, "Good 👍 (1 in 8)": 8},
            16: {"poop 💩 (1 in 123)": 5, "Nice 😂 (1 in 69)": 7},
            17: {"Gilded 💛 (1 in 128)": 6},
            18: {"Legendary 🏅 (1 in 256)": 2, "Epic 🟣 (1 in 32)": 4, "Rare 🔵 (1 in 16)": 8, "Uncommon 🟢 (1 in 4)": 16, "Common ⚪ (1 in 2)": 32},
            19: {"Pi 🥧 (1 in 314)": 3, "Hot ☀ (1 in 40)": 14},
            20: {"Ruby 🔶 (1 in 512)": 2, "ERROR ⚠ (1 in 404)": 4, "Nice 😂 (1 in 69)": 6, "Common ⚪ (1 in 2)": 25}, # super buffed (atleast 1 in 500)
            21: {"Ruby 🔶 (1 in 512)": 3, "Legendary 🏅 (1 in 256)": 6},
            22: {":53: [II] (1 in 530)": 5, ":53: (1 in 53)": 3},
            23: {"Anger 😡 (1 in 600)": 3, "Hot ☀ (1 in 40)": 6, "Cool 😎 (1 in 25)": 20},
            24: {"Freezing ❄️ (1 in 650)": 4, "Anger 😡 (1 in 600)": 4},
            25: {"Jackpot 🤑 (1 in 777)": 3, "Hell 🔥 (1 in 666)": 3, "Hot ☀ (1 in 40)": 10},
            26: {"Money 💵 (1 in 888)": 3, "Jackpot 🤑 (1 in 777)": 2, "Gilded 💛 (1 in 128)": 18},
            27: {"Ruby 🔶 (1 in 512)": 4, "Emerald 🟢 (1 in 512)": 4, "Sapphire 🔹 (1 in 512)": 4},
            28: {"Mythic ✨ (1 in 1,024)": 3, "Ruby 🔶 (1 in 512)": 2, "Emerald 🟢 (1 in 512)": 2, "Sapphire 🔹 (1 in 512)": 2},
            29: {"Mythic ✨ (1 in 1,024)": 4},
            30: {"Exceptional 😱 (1 in 1,500)": 5, "Mythic ✨ (1 in 1,024)": 3, "Lucky 🍀 (1 in 1,000)": 7}, # super buffed (1/1,000 range)
            31: {"Exceptional 😱 (1 in 1,500)": 2},
            32: {"Crystallize 🔮 (1 in 1,248)": 4, "Prestigeous 💠 (1 in 124)": 25, "Uncommon 🟢 (1 in 4)": 50},
            33: {"2048 🔢 (1 in 2,048)": 2, "Common ⚪ (1 in 2)": 100},
            34: {"2048 🔢 (1 in 2,048)": 2, "poop 💩 (1 in 123)": 20},
            35: {"Insane 😮 (1 in 3,800)": 2, "Jackpot 🤑 (1 in 777)": 7, "Freezing ❄️ (1 in 650)": 10},
            36: {"Triangle 🔺 (1 in 3,000)": 3, "Square 🟥 (1 in 4,000)": 4, "Exceptional 😱 (1 in 1,500)": 5},
            37: {"Archaic ❇️ (1 in 5,125)": 2, "Unique 💖 (1 in 5,000)": 3, "Lucky 🍀 (1 in 1,000)": 6, "Money 💵 (1 in 888)": 7},
            38: {"Aureum 💎 (1 in 4,096)": 3, "Crystallize 🔮 (1 in 1,248)": 5},
            39: {":53: [III] (1 in 5,353)": 3, ":53: (1 in 53)": 53},
            40: {"Ultimate  (1 in 8,192)": 1, "Very Nice 😏 (1 in 6,900)": 3, "Archaic ❇️ (1 in 5,125)": 4, "Triangle 🔺 (1 in 3,000)": 1, "Square 🟥 (1 in 4,000)": 1, "KROMER 💰 (1 in 1,997)": 4, "ERROR ⚠ (1 in 404)": 10,  "Good 👍 (1 in 8)": 100}, # super buffed (1/5,000 range) 
            41: {"128-Bit ✯🖥⚠✯ (1 in 340.28Ud)": 1}, # stuff beyond may be unbalanced because i didnt update them yet
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
            3: {"Gilded 💛 (1 in 128)": 8, "Emerald 🟢 (1 in 512)": 4},
            4: {"Epic 🟣 (1 in 32)": 27, "Anger 😡 (1 in 600)": 14, "Lucky 🍀 (1 in 1,000)": 6, "Exceptional 😱 (1 in 1,500)": 3},
            5: {"Aureum 💎 (1 in 4,096)": 8, ":53: [III] (1 in 5,353)": 5, "Ultimate  (1 in 8,192)": 3, "Godly 🤩 (1 in 21,500)": 1}
        },
        "effect": lambda tier, user: {
            "luck_bonus": ((tier or 0) ** 0.2) * 0.1
        },
    }
}
