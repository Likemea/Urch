# Urch/register_commands.py
import requests
import json
import config

APPLICATION_ID = "1228418730103541780"
BOT_TOKEN = config.BOT_TOKEN

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

# 0=GUILD_INSTALL, 1=USER_INSTALL
INTEGRATION_TYPES = [0, 1]

# 0=GUILD, 1=BOT_DM, 2=PRIVATE_CHANNEL
CONTEXTS = [0, 1, 2]

# --- COMMANDS LIST ---
commands = [
    {
        "name": "autoroll",
        "type": 1,
        "description": "Toggle background rolling",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "pixel",
        "type": 1,
        "description": "Generate a 256x256 image of randomly-colored pixels",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {"name": "seed", "description": "Seed for RNG", "type": 4, "required": False},
            {"name": "size", "description": "Image resolution", "type": 4, "required": False},
            {"name": "palette", "description": "Color palette", "type": 3, "required": False},
            {"name": "pattern", "description": "Pattern", "type": 3, "required": False},
        ],
    },
    {
        "name": "roll",
        "type": 1,
        "description": "Roll for a rarity",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "sort",
        "type": 1,
        "description": "Visualize a sorting algorithm",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "size",
                "description": "Size of the array to be sorted",
                "type": 4,
                "required": True,
            },
            {
                "name": "algorithm",
                "description": "Sorting algorithm to use",
                "type": 3,
                "required": False,
                "choices": [
                    {"name": "Bubble", "value": "bubble"},
                    {"name": "Selection", "value": "selection"},
                    {"name": "Insertion", "value": "insertion"},
                    {"name": "Merge", "value": "merge"},
                    {"name": "Quick", "value": "quick"},
                    {"name": "Heap", "value": "heap"},
                    {"name": "Cocktail", "value": "cocktail"},
                    {"name": "Gnome", "value": "gnome"},
                    {"name": "Shell", "value": "shell"},
                ],
            },
        ],
    },
    {
        "name": "filter",
        "type": 1,
        "description": "Apply a filter to an avatar",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "style",
                "description": "The style to apply",
                "type": 3,
                "required": True,
                "choices": [
                    {"name": "Blur", "value": "blur"},
                    {"name": "Contour", "value": "contour"},
                    {"name": "Detail", "value": "detail"},
                    {"name": "Edge Enhance", "value": "edge_enhance"},
                    {"name": "Grayscale", "value": "grayscale"},
                    {"name": "Invert", "value": "invert"},
                    {"name": "Sepia", "value": "sepia"},
                    {"name": "Posterize", "value": "posterize"},
                    {"name": "Solarize", "value": "solarize"},
                ],
            },
            {"name": "user", "description": "The user to filter", "type": 6, "required": False},
        ],
    },
    {
        "name": "ask",
        "type": 1,
        "description": "Ask Urch something",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {"name": "prompt", "description": "Your prompt", "type": 3, "required": True},
        ],
    },
    {
        "name": "settings",
        "type": 1,
        "description": "Change Urch's personality",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "action",
                "description": "View or edit",
                "type": 3,
                "required": True,
                "choices": [{"name": "View", "value": "view"}, {"name": "Edit", "value": "edit"}],
            }
        ],
    },
    {
        "name": "wipe",
        "type": 1,
        "description": "Clear short-term memory",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "inventory",
        "type": 1,
        "description": "View your current rarities",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "upgrades",
        "type": 1,
        "description": "View upgrades",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "checklist",
        "type": 1,
        "description": "View discovery progress",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "recipes",
        "type": 1,
        "description": "Potion and alchemy commands",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "view",
                "description": "Displays all recipes",
                "type": 1,  # SUB_COMMAND
            },
            {
                "name": "craft",
                "description": "Craft a potion from recipes",
                "type": 1,  # SUB_COMMAND
                "options": [
                    {
                        "name": "recipe_id",
                        "description": "The recipe ID of the potion to craft",
                        "type": 3,  # STRING
                        "required": True,
                        "autocomplete": True,
                    },
                    {
                        "name": "amount",
                        "description": "The amount of potions to craft (1-1000)",
                        "type": 4,  # INTEGER
                        "required": False,
                        "min_value": 1,
                        "max_value": 1000,
                    },
                ],
            },
        ],
    },
    {
        "name": "setluck",
        "type": 1,
        "description": "Set your effective luck",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [{"name": "value", "description": "Luck value", "type": 10, "required": False}],
    },
    {
        "name": "debug",
        "type": 1,
        "description": "Recalculate and fix your luck",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "leaderboard",
        "type": 1,
        "description": "View the leaderboard",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "avatar",
        "type": 1,
        "description": "Get someone's avatar",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "user",
                "description": "The user whose avatar you want",
                "type": 6,  # USER type
                "required": False,
            }
        ],
    },
    {
        "name": "user",
        "type": 1,
        "description": "Get information about a user",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "user",
                "description": "The user to view",
                "type": 6,  # USER type
                "required": False,
            }
        ],
    },
    {
        "name": "stats",
        "type": 1,
        "description": "View bot statistics",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "ocr",
        "type": 1,
        "description": "Extract text from an image attachment",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "file",
                "description": "Upload an image to extract text from",
                "type": 11,  # ATTACHMENT type
                "required": True,
            }
        ],
    },
    {
        "name": "analyze",
        "type": 1,
        "description": "Analyze an image",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "file",
                "description": "The image to analyze",
                "type": 11,  # ATTACHMENT type
                "required": True,
            },
            {
                "name": "prompt",
                "description": "Specific question about the image (Optional)",
                "type": 3,  # STRING type
                "required": False,
            },
        ],
    },
    {
        "name": "help",
        "type": 1,
        "description": "Get a list of available commands",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "txt2img",
        "type": 1,
        "description": "Generate an image via Pollinations",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "prompt",
                "description": "Description of the image you want to generate",
                "type": 3,
                "required": True,
            },
            {
                "name": "model",
                "description": "AI model to use",
                "type": 3,
                "required": False,
                "choices": [
                    {"name": "Flux Schnell", "value": "flux"},
                    {"name": "Z-Image Turbo", "value": "zimage"},
                    {"name": "GPT Image 1 Mini", "value": "gptimage"},
                    {"name": "GPT Image 1.5", "value": "gptimage-large"},
                    {"name": "Wan 2.7 Image", "value": "wan-image"},
                    {"name": "Qwen Image Plus", "value": "qwen-image"},
                    {"name": "FLUX.2 Klein 4B", "value": "klein"},
                    {"name": "FLUX.1 Kontext", "value": "kontext"},
                ],
            },
            {
                "name": "width",
                "description": "Width of the image (128-768)",
                "type": 4,
                "required": False,
            },
            {
                "name": "height",
                "description": "Height of the image (128-768)",
                "type": 4,
                "required": False,
            },
            {
                "name": "seed",
                "description": "Seed for reproducible results (-1 for random)",
                "type": 4,
                "required": False,
            },
            {
                "name": "enhance",
                "description": "Urch prompt enhancement",
                "type": 5,
                "required": False,
            },
            {
                "name": "quality",
                "description": "Image quality (low/medium/high) - gpt-image only",
                "type": 3,
                "required": False,
                "choices": [
                    {"name": "Low", "value": "low"},
                    {"name": "Medium", "value": "medium"},
                    {"name": "High", "value": "high"},
                ],
            },
        ],
    },
    {
        "name": "glitch",
        "type": 1,
        "description": "Glitch an image or GIF",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "image",
                "description": "The image or GIF to glitch",
                "type": 11,  # ATTACHMENT type
                "required": True,
            },
            {
                "name": "intensity",
                "description": "How glitchy it should be (1-10)",
                "type": 4,  # INTEGER type
                "required": False,
            },
        ],
    },
    {
        "name": "OCR",
        "type": 3,  # 3 = MESSAGE CONTEXT MENU
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "Analyze Image",
        "type": 3,  # 3 = MESSAGE CONTEXT MENU
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "safety",
        "type": 1,
        "description": "🔒 Owner control panel",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "transcribe",
        "type": 1,
        "description": "Transcribe an audio file attachment",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "file",
                "description": "Upload an audio file to transcribe (.mp3, .wav, .m4a, .ogg, etc.)",
                "type": 11,  # ATTACHMENT type
                "required": True,
            }
        ],
    },
    {
        "name": "Transcribe",
        "type": 3,  # 3 = MESSAGE CONTEXT MENU
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
    },
    {
        "name": "diagnose",
        "type": 1,
        "description": "Run a performance test on the bot's health",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "duration",
                "description": "Duration of diagnostics in seconds (1-60)",
                "type": 4,  # INTEGER
                "required": False,
            }
        ],
    },
]

headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

print(f"⏳ Updating ({len(commands)}) commands.")

response = requests.put(url, headers=headers, json=commands)

if response.status_code in [200, 201]:
    print("✅ All commands updated")
    print("It may take up to 1 hour for changes to appear in all clients")
else:
    print(f"❌ FAILED {response.status_code}")
    print(json.dumps(response.json(), indent=2))
