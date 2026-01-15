"""
Initialize database schema via SQLAlchemy models.

Usage:
  python scripts/init_db.py --db path/to/exam.db
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app import create_app, db


def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    if "://" in db_value:
        return db_value
    path = Path(db_value).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize SQLite schema.")
    parser.add_argument("--db", help="Path to sqlite db file.")
    parser.add_argument(
        "--config",
        default="default",
        help="Config name: development|production|local_admin|default",
    )
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)
    app = create_app(
        args.config,
        db_uri_override=db_uri,
        skip_migration_check=True,
    )
    with app.app_context():
        db.create_all()
    print("Schema initialized.")


if __name__ == "__main__":
    main()
