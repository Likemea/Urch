ITEM_DATA = {
    "diesel": {
        "name": "Diesel",
        "description": "Tier 1 Refinery Fuel",
    },
}

REFINERY_RECIPES = {
    "diesel_recipe": {
        "input": {"charge": 1},
        "output": {"diesel": 1},
        "base_time": 10,
    },
    "diesel_superlarp" = {
        "input": {"charge": 100000},
        "output": {"diesel": 1},
        "base_time": 1,
    }
}

REFINERY_TABS = [
    {  # tab 0: refinery fuel
        "recipes": {
            "diesel": {"diesel_recipe"},
        }
    },
]
