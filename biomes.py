# Urch/biomes.py
import random
import time
from typing import Dict, Any, List, Optional
import discord

from raritylist import RARITIES

RARITY_ID_TO_NAME = {r[2]: r[0] for r in RARITIES}
RARITY_NAME_TO_ID = {r[0]: r[2] for r in RARITIES}

BIOME_COOLDOWN_MIN = 2 * 3600
BIOME_COOLDOWN_MAX = 4 * 3600

BIOME_DURATION_MIN = 15 * 60
BIOME_DURATION_MAX = 30 * 60

BIOME_MULT_MIN = 3
BIOME_MULT_MAX = 10

BIOMES: Dict[str, Dict[str, Any]] = {
    "jotunn_frost": {
        "name": "Jötunn Permafrost",
        "emoji": "❄️",
        "description": "An ancient sub-zero blizzard freezes the realm, awakening glacial rarities.",
        "color": 0x5DADEC,
        "rarities": [
            "freezing",
            "spectral",
            "jotunn",
            "ice_guardian",
            "frozen_gem",
            "cryogenesis",
            "frost_king",
        ],
    },
    "solar_flare": {
        "name": "Solar Flare",
        "emoji": "☀️",
        "description": "Blinding stellar radiation floods the atmosphere, supercharging astrophysical rarities.",
        "color": 0xFFAC33,
        "rarities": [
            "hot",
            "space",
            "planetary",
            "interstellar",
            "light",
            "luminary",
            "galactic",
            "radiant",
            "quasar",
            "big_bang",
            "plasmatic",
            "star_vortex",
            "supernova",
            "sirius_a",
            "supercluster",
            "starstruck",
            "ton618",
        ],
    },
    "subatomic_storm": {
        "name": "Subatomic Fallout",
        "emoji": "☢️",
        "description": "Quantum particles and exotic elements collide in a chain reaction.",
        "color": 0x77B255,
        "rarities": [
            "quantum",
            "subatomic",
            "radioactive",
            "irradiated",
            "baryonic",
            "uu_matter",
            "dark_matter",
            "matter",
            "antimatter",
            "hydrogen",
            "helium",
            "lithium",
            "beryllium",
            "boron",
            "carbon",
            "nitrogen",
            "oxygen",
            "fluorine",
            "neon",
            "lutetium",
        ],
    },
    "cyber_anomaly": {
        "name": "Anomaly Glitch",
        "emoji": "👾",
        "description": "Source code error leaks",
        "color": 0xAA8ED6,
        "rarities": [
            "error",
            "2048",
            "binary",
            "redacted",
            "failure",
            "deletion",
            "matrix",
            "uncomputable",
            "32_bit",
            "tensor",
            "chaos_integer",
            "wordsy",
            "obfuscated",
            "distortion",
            "terminal",
            "scalar",
            "64_bit",
            "vector",
            "scammer",
            "hologram",
            "binary_2",
            "128_bit",
        ],
    },
    "golden_jackpot": {
        "name": "Golden Jackpot",
        "emoji": "🍀",
        "description": "A shimmering aurora of pure fortune rains clovers, gems, and jackpots.",
        "color": 0xFDCB58,
        "rarities": [
            "gilded",
            "ruby",
            "emerald",
            "sapphire",
            "jackpot",
            "money",
            "lucky",
            "kromer",
            "aureum",
            "lottery",
            "crystalline_clover",
            "diamantine",
            "emeradic",
            "true_lottery",
            "hyper_clover",
            "zillionaire",
            "pristine",
        ],
    },
    "dimensional_rift": {
        "name": "Multiversal Rift",
        "emoji": "🌌",
        "description": "The boundaries between parallel universes tear open, pulling in transcendent rarities.",
        "color": 0x9266CC,
        "rarities": [
            "otherworldly",
            "universal",
            "transcendant",
            "temporal",
            "singularity",
            "quintessence",
            "entropy",
            "multiversal",
            "megaversal",
            "gigaversal",
            "gallifreyan",
            "omniversal",
            "hyperversal",
            "octessence",
            "snapping_back_to_reality",
        ],
    },
    "cataclysmic_tempest": {
        "name": "Cataclysmic Tempest",
        "emoji": "⚡",
        "description": "Thunderous infernal energy surges across the sky, empowering volatile rarities.",
        "color": 0xDD2E44,
        "rarities": [
            "anger",
            "hell",
            "charge",
            "unholy",
            "cataclysmic",
            "criticality",
            "raijin",
            "limitless_power",
            "damned",
            "geomaelstrom",
            "1_million_volts",
            "extremity",
        ],
    },
    "the_53_apparition": {
        "name": "The 53 Apparition",
        "emoji": "🔢",
        "description": "53 appears",
        "color": 0x3B88C3,
        "rarities": [
            "53",
            "53_2",
            "53_3",
            "53_4",
            "53_5",
            "53_6",
            "53_7",
            "pi",
            "true_pi",
            "archimedes",
            "skewes",
        ],
    },
}


_current_biome: Optional[Dict[str, Any]] = None
_next_biome_timestamp: float = time.time() + random.randint(BIOME_COOLDOWN_MIN, BIOME_COOLDOWN_MAX)


def get_active_biome(now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Returns the currently active biome dict if one is running, or None if expired/inactive.
    """
    global _current_biome, _next_biome_timestamp
    if now is None:
        now = time.time()

    if _current_biome is not None:
        if now >= _current_biome["ends_at"]:
            if _next_biome_timestamp <= _current_biome["ends_at"]:
                _next_biome_timestamp = _current_biome["ends_at"] + random.randint(
                    BIOME_COOLDOWN_MIN, BIOME_COOLDOWN_MAX
                )
            _current_biome = None
            return None
        return _current_biome

    return None


def get_next_biome_timestamp() -> float:
    """Returns the unix timestamp for when the next biome will trigger."""
    return _next_biome_timestamp


def set_next_biome_timestamp(ts: float) -> None:
    """Sets the unix timestamp for the next scheduled biome trigger."""
    global _next_biome_timestamp
    _next_biome_timestamp = float(ts)


def clear_active_biome() -> None:
    """Clears any active biome immediately."""
    global _current_biome
    _current_biome = None


def trigger_biome(
    biome_id: Optional[str] = None,
    multiplier: Optional[float] = None,
    duration_seconds: Optional[int] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Starts a server-wide biome event and returns the active biome state dict.
    """
    global _current_biome, _next_biome_timestamp
    if now is None:
        now = time.time()

    if not biome_id or biome_id not in BIOMES:
        biome_id = random.choice(list(BIOMES.keys()))

    defn = BIOMES[biome_id]

    if multiplier is None:
        multiplier = float(random.randint(BIOME_MULT_MIN, BIOME_MULT_MAX))
    else:
        multiplier = max(float(BIOME_MULT_MIN), min(float(BIOME_MULT_MAX), float(multiplier)))

    if duration_seconds is None:
        duration_seconds = random.randint(BIOME_DURATION_MIN, BIOME_DURATION_MAX)
    else:
        duration_seconds = max(1, int(duration_seconds))

    boosted_ids = set(defn["rarities"])
    boosted_names = {RARITY_ID_TO_NAME[rid] for rid in boosted_ids if rid in RARITY_ID_TO_NAME}

    _current_biome = {
        "id": biome_id,
        "name": defn["name"],
        "emoji": defn["emoji"],
        "description": defn["description"],
        "color": defn["color"],
        "multiplier": multiplier,
        "started_at": now,
        "ends_at": now + duration_seconds,
        "duration_seconds": duration_seconds,
        "rarity_ids": boosted_ids,
        "rarity_names": boosted_names,
    }

    _next_biome_timestamp = _current_biome["ends_at"] + random.randint(
        BIOME_COOLDOWN_MIN, BIOME_COOLDOWN_MAX
    )
    return _current_biome


def check_and_advance_biome(now: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Called periodically by the bot heartbeat.
    Expires finished biomes and triggers a new biome if _next_biome_timestamp has been reached.
    Returns the newly triggered biome dict if one just started, else None.
    """
    if now is None:
        now = time.time()

    active = get_active_biome(now=now)
    if active is not None:
        return None

    if now >= _next_biome_timestamp:
        return trigger_biome(now=now)

    return None


def format_active_biome_banner(now: Optional[float] = None) -> Optional[str]:
    """
    Returns a compact 1-line summary of the active biome for embeds/footers, or None.
    e.g. '❄️ Jötunn Permafrost (x5 • 18m 42s)'
    """
    if now is None:
        now = time.time()
    active = get_active_biome(now=now)
    if not active:
        return None

    rem = max(0, int(active["ends_at"] - now))
    m, s = divmod(rem, 60)
    time_str = f"{m}m {s}s" if m > 0 else f"{s}s"
    mult_val = active["multiplier"]
    mult_str = f"x{int(mult_val)}" if float(mult_val).is_integer() else f"x{mult_val:.1f}"
    return f"{active['emoji']} {active['name']} ({mult_str} • {time_str})"

