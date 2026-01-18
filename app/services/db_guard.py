from __future__ import annotations

from flask import current_app, request, jsonify, abort
import logging

from config import get_config

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_production() -> bool:
    return current_app.config.get("ENV_NAME") == "production"


def _reject(code: str, message: str):
    payload = {"ok": False, "code": code, "message": message}

    accepts_json = request.is_json or "application/json" in request.headers.get(
        "Accept", ""
    )
    if accepts_json:
        return jsonify(payload), 503

    return abort(503, message)


def guard_write_request(message: str | None = None):
    if request.method not in WRITE_METHODS:
        return None

    if get_config().runtime.db_read_only:
        return _reject("DB_READ_ONLY", message or "Database is in read-only mode.")

    if _is_production():
        auto_backup = get_config().runtime.auto_backup_before_write
        enforce_backup = get_config().runtime.enforce_backup_before_write
        if not auto_backup:
            logging.warning(
                "AUTO_BACKUP_BEFORE_WRITE is disabled in production for %s",
                request.endpoint,
            )

    return None
