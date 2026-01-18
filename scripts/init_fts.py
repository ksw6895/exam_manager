"""
Initialize SQLite FTS5 table for lecture chunks.

SAFETY: DESTRUCTIVE (if --rebuild specified)

Usage:
  python scripts/init_fts.py --sync
  python scripts/init_fts.py --rebuild
  python scripts/init_fts.py --db path/to/exam.db --rebuild
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Removed: from config import Config (now using config package)


def _resolve_db_path(db_arg: str | None) -> str:
    if db_arg:
        return db_arg

    from config import Config as _LegacyConfig

    uri = _LegacyConfig.SQLALCHEMY_DATABASE_URI
    if uri.startswith("sqlite:///"):
        return uri.replace("sqlite:///", "", 1)
    if uri.startswith("sqlite://"):
        return uri.replace("sqlite://", "", 1)
    parsed = urlparse(uri)
    return parsed.path


def _table_exists(cursor: sqlite3.Cursor, name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    )
    return cursor.fetchone() is not None


def init_fts(db_path: str, rebuild: bool, sync: bool, dry_run: bool = False) -> None:
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        raise RuntimeError(f"SQLite DB not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS lecture_chunks_fts
        USING fts5(
            content,
            chunk_id UNINDEXED,
            lecture_id UNINDEXED,
            page_start UNINDEXED,
            page_end UNINDEXED
        )
        """
    )

    if rebuild:
        cursor.execute("DELETE FROM lecture_chunks_fts")

    if sync:
        if not _table_exists(cursor, "lecture_chunks"):
            print("lecture_chunks table not found; skipping sync.")
        else:
            cursor.execute(
                "SELECT id, lecture_id, page_start, page_end, content FROM lecture_chunks"
            )
            rows = cursor.fetchall()
            if not dry_run:
                cursor.executemany(
                    """
                    INSERT INTO lecture_chunks_fts
                        (content, chunk_id, lecture_id, page_start, page_end)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (content, chunk_id, lecture_id, page_start, page_end)
                        for chunk_id, lecture_id, page_start, page_end, content in rows
                    ],
                )
                print(f"Synchronized {len(rows)} chunks into FTS.")
            else:
                print(f"[DRY-RUN] Would synchronize {len(rows)} chunks into FTS.")

    if not dry_run:
        conn.commit()
        conn.close()
        print("FTS init complete.")
    else:
        print("[DRY-RUN] Skipping commit and close")


def main() -> None:
    try:
        from scripts._safety import print_script_header
    except ModuleNotFoundError:
        from _safety import print_script_header

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sync", action="store_true", help="Sync lecture_chunks into FTS."
    )
    parser.add_argument("--rebuild", action="store_true", help="Clear FTS before sync.")
    parser.add_argument("--db", help="Path to sqlite db file.")
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

    print_script_header("init_fts.py", _resolve_db_path(args.db))

    init_fts(
        _resolve_db_path(args.db),
        rebuild=args.rebuild,
        sync=args.sync or args.rebuild,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
