from __future__ import annotations

from flask import current_app, request, jsonify, abort

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def guard_write_request(message: str | None = None):
    if request.method not in WRITE_METHODS:
        return None
    if not current_app.config.get("DB_READ_ONLY", False):
        return None

    payload = {
        "ok": False,
        "code": "DB_READ_ONLY",
        "message": message or "Database is in read-only mode.",
    }

    accepts_json = request.is_json or "application/json" in request.headers.get(
        "Accept", ""
    )
    if accepts_json:
        return jsonify(payload), 503

    return abort(503, payload["message"])
