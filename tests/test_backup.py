# tests/test_backup.py
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backup import PREFIX, backup_database, backup_database_sync


@pytest.fixture
def dummy_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_bot_data.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users (name) VALUES ('urch_tester')")
    return db_file


def test_backup_nonexistent_database(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.db"
    backup_dir = tmp_path / "backups"
    result = backup_database_sync(db_path=non_existent, backup_dir=backup_dir)
    assert result is None
    assert not backup_dir.exists()


def test_backup_database_success(dummy_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    result = backup_database_sync(db_path=dummy_db, backup_dir=backup_dir, keep=3)

    assert result is not None
    assert result.exists()
    assert result.suffix == ".db"
    assert not list(backup_dir.glob("*.tmp"))

    with sqlite3.connect(result) as conn:
        row = conn.execute("SELECT name FROM users WHERE id = 1").fetchone()
        assert row is not None
        assert row[0] == "urch_tester"


def test_backup_rotation(dummy_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for i in range(5):
        old_file = backup_dir / f"{PREFIX}2026010{i}_000000.db"
        old_file.write_text("fake db content")

    assert len(list(backup_dir.glob(f"{PREFIX}*.db"))) == 5

    result = backup_database_sync(db_path=dummy_db, backup_dir=backup_dir, keep=3)
    assert result is not None

    remaining = sorted(backup_dir.glob(f"{PREFIX}*.db"))
    assert len(remaining) == 3
    assert result in remaining


def test_backup_cleans_stale_tmp(dummy_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    stale_tmp = backup_dir / f"{PREFIX}20261029_120000.db.tmp"
    stale_tmp.write_text("leftover temporary data")
    assert stale_tmp.exists()

    result = backup_database_sync(db_path=dummy_db, backup_dir=backup_dir)
    assert result is not None
    assert not stale_tmp.exists()
    assert not list(backup_dir.glob("*.tmp"))


def test_backup_failure_cleans_up_tmp(dummy_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    real_connect = sqlite3.connect

    class FailingConnection:
        def __init__(self, *args, **kwargs):
            self.conn = real_connect(*args, **kwargs)

        def backup(self, *args, **kwargs):
            raise sqlite3.OperationalError("Simulated disk error or corruption")

        def close(self):
            self.conn.close()

    with patch("backup.sqlite3.connect", side_effect=FailingConnection):
        with pytest.raises(sqlite3.OperationalError, match="Simulated disk error"):
            backup_database_sync(db_path=dummy_db, backup_dir=backup_dir)

    assert not list(backup_dir.glob("*.tmp"))


@pytest.mark.asyncio
async def test_backup_database_async(dummy_db: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    result = await backup_database(db_path=dummy_db, backup_dir=backup_dir)
    assert result is not None
    assert result.exists()
