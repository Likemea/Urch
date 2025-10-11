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
            35: {"Insane 😮 (1 in 3,800)": 2, "Jackpot 🤑 (1 in 777)": 7, "Freezing ❄️ (1 in 650)": 10},                                   # 19,539 difficulty
            36: {"Triangle 🔺 (1 in 3,000)": 3, "Square 🟥 (1 in 4,000)": 4, "Exceptional 😱 (1 in 1,500)": 5},                            # 32,500 difficulty
            37: {"Archaic ❇️ (1 in 5,125)": 2, "Unique 💖 (1 in 5,000)": 3, "Lucky 🍀 (1 in 1,000)": 6, "Money 💵 (1 in 888)": 7},        # 37,466 difficulty
            38: {"Aureum 💎 (1 in 4,096)": 3, "Crystallize 🔮 (1 in 1,248)": 5},                                                           # 18,528 difficulty
            39: {":53: [III] (1 in 5,353)": 3, ":53: (1 in 53)": 53},                                                                       # 18,868 difficulty
            40: {"Ultimate  (1 in 8,192)": 1, "Very Nice 😏 (1 in 6,900)": 3, "Archaic ❇️ (1 in 5,125)": 4, "Triangle 🔺 (1 in 3,000)": 1, "Square 🟥 (1 in 4,000)": 1, "KROMER 💰 (1 in 1,997)": 4, "ERROR ⚠ (1 in 404)": 10,  "Good 👍 (1 in 8)": 100}, # 69,220 difficulty  
            41: ("Exotic 🫠 (1 in 9,999)": 2, "Mythic ✨ (1 in 1,024)": 7),                                                                 # 27,166 diff.                                                                   
            42: {"Exode 🌠 (1 in 10,000)": 2, "Extreme 🧗🏻‍♂️ (1 in 7,009)": 3, "2048 🔢 (1 in 2,048)": 4},                                    # 49,219 diff.        
            43: {"Unusual 🔎 (1 in 16,384)": 1, "Grass 🌱 (1 in 12,345)": 3},                                                              # 53,359 diff.
            44: {"Superman 🦸‍♂️ (1 in 12,228)": 3, "Exotic 🫠 (1 in 9,999)": 2, "Very Nice 😏 (1 in 6,900)": 3, "Man 👨 (1 in 100)": 50},    # 82,382 diff.
            45: {"Continental 🗺️ (1 in 27,000)": 2, "Unusual 🔎 (1 in 16,384)": 4},                                                        # 119,536 diff.
            46: {"Archidon 🌌 (1 in 22,500)": 1, "Godly 🤩 (1 in 21,500)": 1, "Pi 🥧 (1 in 314)": 31, "poop 💩 (1 in 123)": 1},           # 53,857 diff. significantly easier :3
            47: {"Binary 💻 (1 in 32,768)": 2, "Exode 🌠 (1 in 10,000)": 4, "Square 🟥 (1 in 4,000)": 8, "Aureum 💎 (1 in 4,096)": 10},        # 145,728 diff.
            48: {"Enigmatic 🧩 (1 in 40,404)": 2, "Quantum ⚛️ (1 in 33,333)": 2, "Binary 💻 (1 in 32,768)": 1, "Godly 🤩 (1 in 21,500)": 3},   # 244,742 diff.
            49: {":53: [IV] (1 in 53,530)": 3, ":53: [III] (1 in 5,353)": 5, ":53: [II] (1 in 530)": 25, ":53: (1 in 53)": 53},                  # 205,905 diff.
            50: {"Divine 🌃 (1 in 65,536)": 3, ":53: [IV] (1 in 53,530)": 1, "Otherworldly 🫧 (1 in 44,444)": 4, "Enigmatic 🧩 (1 in 40,404)": 1, "Quantum ⚛️ (1 in 33,333)": 1, "Binary 💻 (1 in 32,768)": 1, "Continental 🗺️ (1 in 27,000)": 1, "Archidon 🌌 (1 in 22,500)": 2, "Godly 🤩 (1 in 21,500)": 2}, # 518,347 diff.
            51: {"Ascendant 👼 (1 in 72,000)": 2, "Exode 🌠 (1 in 10,000)": 5},                                   # 194,000 diff.
            52: {"Unfathomable 🚰 (1 in 75,000)": 1, "Divine 🌃 (1 in 65,536)": 1, "Extreme 🧗🏻‍♂️ (1 in 7,009)": 6}, # 182,590 diff.
            53: {"Miner ⛏ (1 in 90,100)": 5, ":53: [IV] (1 in 53,530)": 3, ":53: [III] (1 in 5,353)": 53, ":53: (1 in 53)": 69}, # ~611,090 diff.
            54: {"Steel 🔩 (1 in 123,456)": 3, "Grass 🌱 (1 in 12,345)": 7},                                       # 456,783 diff.
            55: {"Easy 😃 (1 in 131,072)": 4, "Archidon 🌌 (1 in 22,500)": 10, "Good 👍 (1 in 8)": 1},            # 749,296 diff.
            56: {"negus 🥶 (1 in 140,000)": 4, "Steel 🔩 (1 in 123,456)": 2, "Freezing ❄️ (1 in 650)": 100},      # 871,912 diff.
            57: {"Supreme 🪐 (1 in 350,000)": 5, "Skilled 🤸‍♂️ (1 in 262,144)": 3},                                 # 2,536,432 diff.
            58: {"Common ⚪ (1 in 2)": 1},                                                                        # 2
            59: {"Unstoppable ❌ (1 in 500,000)": 2, "Charge ⚡ (1 in 444,444)": 4},                              # 2,777,776 diff.
            60: {":53: [V] (1 in 530,530)": 5, "Slick 🤪 (1 in 524,288)": 3, "Redacted ⬛ (1 in 200,000)": 7},    # 5,625,514 diff.
            61: {"ifinity (1 in 1)": 9999999999999, "Common ⚪ (1 in 2)": 61272002009999488}                      # infinite :sli:
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
            5: {"Aureum 💎 (1 in 4,096)": 8, ":53: [III] (1 in 5,353)": 5, "Ultimate  (1 in 8,192)": 3, "Godly 🤩 (1 in 21,500)": 1},
            6: {"Unfathomable 🚰 (1 in 75,000)": 2, "Divine 🌃 (1 in 65,536)": 3, "Otherworldly 🫧 (1 in 44,444)": 4, "Enigmatic 🧩 (1 in 40,404)": 4},
            7: {"Planetary 🌍 (1 in 1,000,000)": 1, "Redacted ⬛ (1 in 200,000)": 4, "Steel 🔩 (1 in 123,456)": 4, "Miner ⛏ (1 in 90,100)": 5, ":53: [IV] (1 in 53,530)": 3},
            8: {"Radiant 🌟 (1 in 16,777,216)": 1, "Luminary ☀️ (1 in 4,444,444)": 4, "Spectral 🧊🌈 (1 in 2,777,777)": 5, "Infrared ♨️ (1 in 2,475,475)": 5, "Interstellar 🌞 (1 in 1,300,000)": 16}
        },
        "effect": lambda tier, user: {
            "luck_bonus": ((tier or 0) ** 0.2) * 0.1
        },
    }
}
