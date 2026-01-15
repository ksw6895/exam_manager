"""
Clone a SQLite database using the backup API.

Usage:
  python scripts/clone_db.py --db data/exam.db --out data/dev.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]


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


def clone_db(src_path: Path, dest_path: Path) -> None:
    if not src_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {src_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src_path.as_posix()) as src, sqlite3.connect(
        dest_path.as_posix()
    ) as dst:
        src.backup(dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone a SQLite database.")
    parser.add_argument("--db", help="Source sqlite db file.")
    parser.add_argument(
        "--out",
        default=str(ROOT_DIR / "data" / "dev.db"),
        help="Destination db file.",
    )
    args = parser.parse_args()

    src_path = _resolve_db_path(args.db)
    dest_path = Path(args.out)
    clone_db(src_path, dest_path)
    print(f"Cloned {src_path} -> {dest_path}")


if __name__ == "__main__":
    main()
