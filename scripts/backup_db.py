"""
Hot backup for SQLite databases.

Usage:
  python scripts/backup_db.py --db path/to/exam.db --keep 30
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def _resolve_db_path(db_arg: str | None) -> Path:
    if db_arg:
        return Path(db_arg)

    from config import Config

    uri = Config.SQLALCHEMY_DATABASE_URI
    if uri.startswith("sqlite:///"):
        return Path(uri.replace("sqlite:///", "", 1))
    if uri.startswith("sqlite://"):
        return Path(uri.replace("sqlite://", "", 1))
    parsed = urlparse(uri)
    return Path(parsed.path)


def _backup_path(db_path: Path, backup_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return backup_dir / f"{db_path.name}.{timestamp}"


def _prune_backups(backup_dir: Path, db_name: str, keep: int) -> int:
    if keep <= 0:
        return 0
    pattern = f"{db_name}.*"
    backups = sorted(backup_dir.glob(pattern))
    if len(backups) <= keep:
        return 0
    removed = 0
    for path in backups[: len(backups) - keep]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def hot_backup(db_path: Path, backup_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(db_path, backup_dir)

    with sqlite3.connect(db_path.as_posix()) as src, sqlite3.connect(
        backup_path.as_posix()
    ) as dst:
        src.backup(dst)

    _prune_backups(backup_dir, db_path.name, keep)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Hot backup a SQLite database.")
    parser.add_argument("--db", help="Path to sqlite db file.")
    parser.add_argument("--keep", type=int, default=30, help="Keep latest N backups.")
    parser.add_argument(
        "--backup-dir",
        default=str(ROOT_DIR / "backups"),
        help="Directory to store backups.",
    )
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db)
    backup_dir = Path(args.backup_dir)
    backup_path = hot_backup(db_path, backup_dir, args.keep)
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
