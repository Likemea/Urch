# Urch/backup.py
"""
Online SQLite backups with rotation.

Uses sqlite3's backup API on a separate connection, which is safe while the bot's
aiosqlite connection is active (WAL mode). Runs in a worker thread so the event
loop is never blocked.

Can also be run standalone (e.g. from cron): `python backup.py`
"""

import asyncio
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_DB_PATH = BASE_DIR / "bot_data.db"
DEFAULT_BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_KEEP = int(os.environ.get("BACKUP_KEEP", "7"))
PREFIX = "bot_data_"


def backup_database_sync(
    db_path: Path = DEFAULT_DB_PATH,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    keep: int = DEFAULT_KEEP,
) -> Path | None:
    """Create a timestamped backup and delete all but the newest `keep` backups."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"{PREFIX}{time.strftime('%Y%m%d_%H%M%S')}.db"
    tmp = dest.with_suffix(".db.tmp")

    try:
        with closing(sqlite3.connect(db_path)) as src, closing(sqlite3.connect(tmp)) as dst:
            src.backup(dst)
        tmp.replace(dest)  # atomic: never leave a half-written backup behind
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    backups = sorted(backup_dir.glob(f"{PREFIX}*.db"))
    for old in backups[: max(0, len(backups) - keep)]:
        old.unlink(missing_ok=True)

    for stale in backup_dir.glob(f"{PREFIX}*.db.tmp"):
        stale.unlink(missing_ok=True)

    return dest


async def backup_database(**kwargs) -> Path | None:
    return await asyncio.to_thread(backup_database_sync, **kwargs)


if __name__ == "__main__":
    result = backup_database_sync()
    print(f"Backup written: {result}" if result else "No database found, nothing to back up.")
