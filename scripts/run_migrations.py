"""
Run pending SQLite migrations.

Usage:
  python scripts/run_migrations.py --db path/to/exam.db
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import sqlite3

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
MIGRATIONS_DIR = ROOT_DIR / "migrations"


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


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _load_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _fetch_applied(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT version, checksum FROM schema_migrations"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _apply_migration(
    conn: sqlite3.Connection, version: str, sql_text: str, checksum: str
) -> None:
    applied_at = datetime.utcnow().isoformat(timespec="seconds")
    script = "\n".join(
        [
            "BEGIN;",
            sql_text.rstrip().rstrip(";") + ";",
            (
                "INSERT INTO schema_migrations (version, checksum, applied_at) "
                f"VALUES ('{_sql_literal(version)}', '{checksum}', '{applied_at}');"
            ),
            "COMMIT;",
        ]
    )
    conn.executescript(script)


def run_migrations(db_path: Path) -> int:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    migrations = _load_migrations()
    if not migrations:
        print("No migrations found.")
        return 0

    applied_count = 0
    with sqlite3.connect(db_path.as_posix()) as conn:
        _ensure_schema_migrations(conn)
        applied = _fetch_applied(conn)

        for path in migrations:
            version = path.name
            sql_text = path.read_text(encoding="utf-8")
            checksum = _checksum(sql_text)

            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(
                        f"Checksum mismatch for {version}: {applied[version]} != {checksum}"
                    )
                print(f"Skip: {version}")
                continue

            try:
                _apply_migration(conn, version, sql_text, checksum)
            except Exception as exc:
                raise RuntimeError(f"Migration failed: {version}") from exc

            applied_count += 1
            print(f"Applied: {version}")

    return applied_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pending SQLite migrations.")
    parser.add_argument("--db", help="Path to sqlite db file.")
    args = parser.parse_args()

    db_path = _resolve_db_path(args.db)
    count = run_migrations(db_path)
    print(f"Applied {count} migrations.")


if __name__ == "__main__":
    main()
