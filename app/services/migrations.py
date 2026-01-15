from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse


def _resolve_db_path(db_uri: str) -> Path:
    if db_uri.startswith("sqlite:///"):
        return Path(db_uri.replace("sqlite:///", "", 1))
    if db_uri.startswith("sqlite://"):
        return Path(db_uri.replace("sqlite://", "", 1))
    parsed = urlparse(db_uri)
    return Path(parsed.path)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _load_migrations(migrations_dir: Path) -> List[Path]:
    if not migrations_dir.exists():
        return []
    return sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fetch_applied(conn: sqlite3.Connection) -> Dict[str, str]:
    if not _table_exists(conn, "schema_migrations"):
        return {}
    rows = conn.execute(
        "SELECT version, checksum FROM schema_migrations"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def detect_pending_migrations(
    db_uri: str, migrations_dir: Path
) -> Tuple[List[str], List[str]]:
    db_path = _resolve_db_path(db_uri)
    if not db_path.exists():
        return [], []

    migrations = _load_migrations(migrations_dir)
    if not migrations:
        return [], []

    with sqlite3.connect(db_path.as_posix()) as conn:
        applied = _fetch_applied(conn)

    pending = []
    mismatched = []
    for path in migrations:
        version = path.name
        sql_text = path.read_text(encoding="utf-8")
        checksum = _checksum(sql_text)
        if version not in applied:
            pending.append(version)
            continue
        if applied[version] != checksum:
            mismatched.append(version)

    return pending, mismatched


def check_pending_migrations(
    db_uri: str,
    migrations_dir: Path,
    env_name: str,
    logger,
    fail_on_pending: bool,
) -> None:
    db_path = _resolve_db_path(db_uri)
    if not db_path.exists():
        logger.warning("SQLite DB not found; skipping migration check: %s", db_path)
        return

    pending, mismatched = detect_pending_migrations(db_uri, migrations_dir)
    if not pending and not mismatched:
        return

    if pending:
        logger.warning("Pending migrations detected: %s", ", ".join(pending))
    if mismatched:
        logger.warning(
            "Migration checksum mismatch detected: %s", ", ".join(mismatched)
        )

    if env_name == "production" and fail_on_pending:
        raise RuntimeError("Pending or mismatched migrations detected in production.")
