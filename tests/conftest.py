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
    """Provide a fake `config` module so Urch modules can be imported
    without real secrets or a running bot."""
    cfg = types.ModuleType("config")
    cfg.BOT_TOKEN = "test.bot.token"
    cfg.GROQ_API_KEY = "test_groq_key"
    cfg.POLLINATIONS_API_KEY = "test_pollinations_key"
    cfg.GOOGLE_API_KEY = "test_google_key"
    sys.modules["config"] = cfg


_install_config_stub()


@pytest_asyncio.fixture
async def fresh_db(tmp_path, monkeypatch):
    """Isolated SQLite-backed Database. Patches `utils.db` so utils helpers
    operate against the same instance."""
    import database as db_module
    from database import Database
    import utils as utils_module

    test_db = Database(str(tmp_path / "test.db"))
    await test_db.initialize()

    monkeypatch.setattr(db_module, "db", test_db, raising=False)
    monkeypatch.setattr(utils_module, "db", test_db, raising=False)

    try:
        yield test_db
    finally:
        await test_db.close()
