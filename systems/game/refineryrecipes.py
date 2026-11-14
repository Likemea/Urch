ITEM_DATA = {
    "placeholder": {
        "name": "Placeholder",
        "description": "No",
    },
    "diesel": {
        "name": "Diesel",
        "description": "Tier 1 Refinery Fuel",
    },
    "defaultite": {
        "name": "Defaultite",
        "description": "Welcome to the refinery!",
    },
    "cfuel_mk1": {
        "name": "Clover Fuel Mk. I",
        "description": "Fueling the future",
    },
    "cfuel_mk1_depleted": {
        "name": "Depleted Clover Fuel Mk. I",
        "description": "Maybe useful?",
    },
    "cfuel_mk2": {
        "name": "Clover Fuel Mk. II",
        "description": "3 watts per hour",
    },
    "cast_iron": {
        "name": "Cast Iron",
        "description": "Steel, now with higher carbon content!",
    },
}

REFINERY_RECIPES = {
    "placeholder_recipe": {
        "name": "g",
        "input": {"infinity": 1000},
        "output": {"placeholder": 1},
        "base_time": 30000000,
        "tier": 0,
    },
    "defaultite_recipe": {
        "name": "Defaultite Refining",
        "input": {"common": 1},
        "output": {"defaultite": 1},
        "base_time": 1,
        "tier": 1,
    },
    # refinery fuel recipes
    "diesel_recipe": {
        "name": "Diesel Separation",
        "input": {"charge": 1},
        "output": {"diesel": 1},
        "base_time": 0,
        "tier": 0,
    },
    # autoroll fuel recipes
    "cfuel_mk1_recipe": {
        "name": "Clover Fuel Refining I",
        "input": {
            "clovers": 10,
            "steel": 1,
        },
        "output": {"cfuel_mk1": 1},
        "base_time": 60,
        "tier": 1,
    },
    "cfuel_mk2_recipe": {
        "name": "Clover Fuel Refining II",
        "input": {
            "clovers": 75,
            "darkness": 10,
            "infrared": 10,
            "light": 4,
        },
        "output": {
            "cfuel_mk2": 5,
            "luminary": 1,
        },
        "base_time": 240,
        "tier": 2,
    },
    "cfuel_mk2_recipe_depleted": {
        "name": "Depleted Fuel Recycling II",
        "input": {
            "clovers": 40,
            "cfuel_mk1_depleted": 25,
            "darkness": 2,
            "infrared": 2,
            "light": 1,
        },
        "output": {"cfuel_mk2": 5},
        "base_time": 120,
        "tier": 2,
    },
    # compound recipes
    "cast_iron_recipe": {
        "name": "Cast Iron Smelting",
        "input": {
            "steel": 2,
            "coal": 1,
        },
        "output": {"cast_iron": 2},
        "base_time": 360,
        "tier": 1,
    },
    "cast_iron_recipe_efficient": {
        "name": "Cast Iron Smelting 2",
        "input": {
            "steel": 20,
            "carbon": 2,
            "oxygen": 1,
        },
        "output": {"cast_iron": 20},
        "base_time": 120,
        "tier": 23,
    },
}

REFINERY_TABS = [
    {
        "recipes": {
            "defaultite": ["defaultite_recipe"],
        },
    },
    {  # tab 1: refinery fuel
        "recipes": {
            "diesel": ["diesel_recipe"],
        }
    },
    {  # tab 2: autoroll fuel
        "recipes": {
            "cfuel_mk1": ["cfuel_mk1_recipe"],
            "cfuel_mk2": [
                "cfuel_mk2_recipe",
                "cfuel_mk2_recipe_depleted",
            ],
        },
    },
    {  # tab 3: compounds
        "recipes": {
            "cast_iron": [
                "cast_iron_recipe",
                "cast_iron_recipe_efficient",
            ],
        },
    },
    {  # tab 4: items
        "recipes": {
            "placeholder": ["placeholder_recipe"],
        },
    },
    {  # tab 5: misc
        "recipes": {
            "placeholder": ["placeholder_recipe"],
        },
    },
]
