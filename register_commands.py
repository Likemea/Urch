# Urch/register_commands.py
import os
import requests
import json
import time

APPLICATION_ID = '1228418730103541780'
BOT_TOKEN = os.environ.get('BOT_TOKEN') 

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
        "contexts": CONTEXTS
    },
    {
        "name": "pixel",
        "type": 1,
        "description": "Generate a 256x256 image of randomly-colored pixels",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "seed", "description": "Seed for RNG", "type": 4, "required": False
            },
            {
                "name": "size", "description": "Image resolution", "type": 4, "required": False
            },
            {
                "name": "palette", "description": "Color palette", "type": 3, "required": False
            },
            {
                "name": "pattern", "description": "Pattern", "type": 3, "required": False
            }
        ]
    },
    {
        "name": "roll",
        "type": 1,
        "description": "Roll for a rarity",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
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
                "required": True
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
                    {"name": "Shell", "value": "shell"}
                ]
            }
        ]
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
                "description": "The artistic style to apply", 
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
                    {"name": "Solarize", "value": "solarize"}
                ]
            },
            {
                "name": "user", 
                "description": "The user to filter", 
                "type": 6, 
                "required": False
            }
        ]
    },
    {
        "name": "ask",
        "type": 1,
        "description": "Ask Urch something",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {"name": "prompt", "description": "Your prompt", "type": 3, "required": True},
        ]
    },
    {
        "name": "settings",
        "type": 1,
        "description": "View or adjust bot AI parameters",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "action",
                "description": "View or edit",
                "type": 3,
                "required": True,
                "choices": [
                    {"name": "View", "value": "view"},
                    {"name": "Edit", "value": "edit"}
                ]
            }
        ]
    },
    {
        "name": "wipe",
        "type": 1,
        "description": "Clear short-term memory",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "inventory",
        "type": 1,
        "description": "View your current rarities",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "upgrades",
        "type": 1,
        "description": "View upgrades",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "checklist",
        "type": 1,
        "description": "View discovery progress",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "setluck",
        "type": 1,
        "description": "Set your effective luck",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [{"name": "value", "description": "Luck value", "type": 10, "required": False}]
    },
    {
        "name": "debug",
        "type": 1,
        "description": "Recalculate and fix your luck",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "leaderboard",
        "type": 1,
        "description": "View the leaderboard",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
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
                "type": 6, # USER type
                "required": False
            }
        ]
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
                "type": 6, # USER type
                "required": False
            }
        ]
    },
    {
        "name": "stats",
        "type": 1,
        "description": "View bot statistics",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
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
                "type": 11, # ATTACHMENT type
                "required": True
            }
        ]
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
                "type": 11, # ATTACHMENT type
                "required": True
            },
            {
                "name": "prompt",
                "description": "Specific question about the image (Optional)",
                "type": 3, # STRING type
                "required": False
            }
        ]
    },
    {
        "name": "help",
        "type": 1,
        "description": "Get a list of available commands",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "imagine",
        "type": 1,
        "description": "Generate an image",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS,
        "options": [
            {
                "name": "prompt",
                "description": "The description of the image you want to generate",
                "type": 3, # STRING type
                "required": True
            }
        ]
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
                "type": 11, # ATTACHMENT type
                "required": True
            },
            {
                "name": "intensity",
                "description": "How glitchy it should be (1-10)",
                "type": 4, # INTEGER type
                "required": False
            }
        ]
    },
    {
        "name": "OCR",
        "type": 3,  # 3 = MESSAGE CONTEXT MENU
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "Analyze Image",
        "type": 3,  # 3 = MESSAGE CONTEXT MENU
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    },
    {
        "name": "safety",
        "type": 1,
        "description": "🔒 Owner control panel",
        "integration_types": INTEGRATION_TYPES,
        "contexts": CONTEXTS
    }
]

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

print(f"⏳ Overwriting global commands (Batch of {len(commands)})...")

# Using PUT to overwrite ALL commands at once
response = requests.put(url, headers=headers, json=commands)

if response.status_code in [200, 201]:
    print("✅ SUCCESS! All commands have been updated globally.")
    print("NOTE: It may take up to 1 hour for these changes to appear in all clients.")
    print("If commands disappear from Servers, verify 'Integration Types' includes 0 (Guild Install).")
else:
    print(f"❌ FAILED with code {response.status_code}")
    print("Error details:")
    print(json.dumps(response.json(), indent=2))