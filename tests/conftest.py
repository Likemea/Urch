# tests/conftest.py
import sys
import types
from pathlib import Path
import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_config_stub():
    """Provide a fake `systems.core.config` module so Urch modules can be imported
    without real secrets or a running bot."""
    import systems.core

    cfg = types.ModuleType("systems.core.config")
    cfg.APPLICATION_ID = "123456789012345678"
    cfg.BOT_TOKEN = "test.bot.token"
    cfg.GROQ_API_KEY = "test_groq_key"
    cfg.POLLINATIONS_API_KEY = "test_pollinations_key"
    cfg.GOOGLE_API_KEY = "test_google_key"
    sys.modules["systems.core.config"] = cfg
    systems.core.config = cfg


_install_config_stub()


@pytest_asyncio.fixture
async def fresh_db(tmp_path, monkeypatch):
    """Isolated SQLite-backed Database. Patches `systems.core.database.db` and
    `systems.game.utils.db` so helpers operate against the same instance."""
    import systems.core.database as db_module
    from systems.core.database import Database
    import systems.game.utils as utils_module

    test_db = Database(str(tmp_path / "test.db"))
    await test_db.initialize()

    monkeypatch.setattr(db_module, "db", test_db, raising=False)
    monkeypatch.setattr(utils_module, "db", test_db, raising=False)

    # Also patch command modules that imported `db` at top-level if already loaded
    for mod_name in (
        "systems.bot.commands.alchemy",
        "systems.bot.commands.leaderboard",
        "systems.bot.commands.pit",
        "systems.bot.commands.roll",
        "systems.bot.commands.safety",
        "systems.bot.commands.setluck",
        "systems.bot.commands.upgrades",
        "systems.bot.commands.wipe",
        "main",
    ):
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "db"):
            monkeypatch.setattr(mod, "db", test_db, raising=False)

    try:
        yield test_db
    finally:
        await test_db.close()
