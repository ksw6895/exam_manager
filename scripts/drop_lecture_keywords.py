import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _default_db_paths():
    candidates = [Path("data/exam.db"), Path("data/admin_local.db")]
    return [path for path in candidates if path.exists()]


def _has_keywords_column(conn):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(lectures)")]
    return "keywords" in columns


def _backup_db(path):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".bak.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def _drop_keywords(path, no_backup):
    if not path.exists():
        print(f"{path}: missing")
        return

    with sqlite3.connect(path) as conn:
        if not _has_keywords_column(conn):
            print(f"{path}: keywords column not found")
            return

        if not no_backup:
            backup_path = _backup_db(path)
            print(f"{path}: backup -> {backup_path}")

        conn.execute("ALTER TABLE lectures DROP COLUMN keywords")
        print(f"{path}: dropped keywords column")


def main():
    parser = argparse.ArgumentParser(description="Drop lectures.keywords column.")
    parser.add_argument("--db", action="append", help="Path to sqlite db file.")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup before altering the database.",
    )
    args = parser.parse_args()

    targets = [Path(p) for p in (args.db or [])]
    if not targets:
        targets = _default_db_paths()

    if not targets:
        print("No database files found.")
        return

    for path in targets:
        _drop_keywords(path, args.no_backup)


if __name__ == "__main__":
    main()
