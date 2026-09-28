# tests/conftest.py
import sys
import types
import pytest
import pytest_asyncio


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

    test_db = Database(str(tmp_path / "test.db"))
    await test_db.initialize()

    monkeypatch.setattr(db_module, "db", test_db, raising=False)
    try:
        import utils as utils_module

        monkeypatch.setattr(utils_module, "db", test_db, raising=False)
    except ImportError:
        pass

    try:
        yield test_db
    finally:
        await test_db.close()
