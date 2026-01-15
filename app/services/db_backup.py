from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import current_app


def _resolve_db_path(uri: str) -> Path:
    if uri.startswith("sqlite:///"):
        return Path(uri.replace("sqlite:///", "", 1))
    if uri.startswith("sqlite://"):
        return Path(uri.replace("sqlite://", "", 1))
    parsed = urlparse(uri)
    return Path(parsed.path)


def _build_backup_path(db_path: Path, backup_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return backup_dir / f"{db_path.name}.{timestamp}"


def _prune_backups(backup_dir: Path, db_name: str, keep: int) -> None:
    if keep <= 0:
        return
    backups = sorted(backup_dir.glob(f"{db_name}.*"))
    if len(backups) <= keep:
        return
    for path in backups[: len(backups) - keep]:
        path.unlink(missing_ok=True)


def backup_database(db_uri: str, backup_dir: Path, keep: int) -> Path:
    db_path = _resolve_db_path(db_uri)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _build_backup_path(db_path, backup_dir)

    with sqlite3.connect(db_path.as_posix()) as src, sqlite3.connect(
        backup_path.as_posix()
    ) as dst:
        src.backup(dst)

    _prune_backups(backup_dir, db_path.name, keep)
    return backup_path


def maybe_backup_before_write(action: str | None = None) -> Path | None:
    config = current_app.config
    if not config.get("AUTO_BACKUP_BEFORE_WRITE", False):
        return None

    backup_dir = Path(config.get("AUTO_BACKUP_DIR") or "backups")
    keep = int(config.get("AUTO_BACKUP_KEEP") or 30)
    db_uri = config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri:
        return None

    backup_path = backup_database(db_uri, backup_dir, keep)
    current_app.logger.info(
        "Auto-backup created before write%s: %s",
        f" ({action})" if action else "",
        backup_path,
    )
    return backup_path
