"""
Drop lectures.keywords column from database.

SAFETY: DESTRUCTIVE (modifies database schema)

Usage:
  python scripts/drop_lecture_keywords.py --db data/exam.db
  python scripts/drop_lecture_keywords.py --db data/exam.db --no-backup
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
try:
    from scripts._safety import SafetyLevel, require_confirmation, print_script_header
except ModuleNotFoundError:
    from _safety import SafetyLevel, require_confirmation, print_script_header


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


def _drop_keywords(path, no_backup, dry_run=False):
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

        if dry_run:
            print(f"[DRY-RUN] Would drop keywords column from {path}")
            return

        conn.execute("ALTER TABLE lectures DROP COLUMN keywords")
        conn.commit()
        print(f"{path}: dropped keywords column")


def main():
    try:
        from scripts._safety import SafetyLevel
    except ModuleNotFoundError:
        from _safety import SafetyLevel

    parser = argparse.ArgumentParser(description="Drop lectures.keywords column.")
    parser.add_argument("--db", action="append", help="Path to sqlite db file.")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup before altering database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing.",
    )
    parser.add_argument(
        "--yes-i-really-mean-it",
        action="store_true",
        help="Confirm destructive operation.",
    )
    args = parser.parse_args()

    targets = [Path(p) for p in (args.db or [])]
    if not targets:
        targets = _default_db_paths()

    if not targets:
        print("No database files found.")
        return

    print_script_header("drop_lecture_keywords.py")

    if not require_confirmation(
        SafetyLevel.DESTRUCTIVE,
        "drop keywords column from databases",
        env_flag="ALLOW_DESTRUCTIVE",
        cli_flag="--yes-i-really-mean-it" in sys.argv,
        dry_run=args.dry_run,
    ):
        return

    for path in targets:
        _drop_keywords(path, args.no_backup, args.dry_run)


if __name__ == "__main__":
    main()
