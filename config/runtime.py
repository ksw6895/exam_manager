"""Runtime configuration - environment-driven settings.

Reads environment variables and applies defaults for production runtime.
"""

import os
from pathlib import Path

from .base import (
    DEFAULT_SECRET_KEY,
    DEFAULT_DB_URI,
    LOCAL_ADMIN_DB_URI,
    DEFAULT_UPLOAD_FOLDER,
    DEFAULT_LOCAL_ADMIN_UPLOAD_FOLDER,
    DEFAULT_BACKUP_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_CLASSIFIER_CACHE_PATH,
    DEFAULT_MAX_CONTENT_LENGTH,
    DEFAULT_AUTO_BACKUP_KEEP,
    DEFAULT_AUTO_CREATE_DB,
    DEFAULT_GEMINI_MODEL_NAME,
    DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
    DEFAULT_CORS_ALLOWED_ORIGINS,
    DEFAULT_CORS_ALLOWED_ORIGINS_PROD,
)
from .schema import RuntimeConfig


def _env_flag(name, default=False):
    """Read a boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    """Read an integer environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_runtime_config(flask_config_name="default") -> RuntimeConfig:
    """
    Build runtime configuration from environment variables.

    Args:
        flask_config_name: Flask config profile name (default/production/local_admin)
                          Used to select appropriate DB path.

    Returns:
        RuntimeConfig instance
    """
    # Database selection based on Flask profile
    if flask_config_name == "local_admin":
        db_env = os.environ.get("LOCAL_ADMIN_DB")
        db_uri = f"sqlite:///{db_env}" if db_env else LOCAL_ADMIN_DB_URI
        upload_folder = DEFAULT_LOCAL_ADMIN_UPLOAD_FOLDER
        local_admin_only = True
    else:
        db_env = os.environ.get("DB_PATH")  # Optional explicit override
        db_uri = _sqlite_uri(Path(db_env)) if db_env else DEFAULT_DB_URI
        upload_folder = DEFAULT_UPLOAD_FOLDER
        local_admin_only = _env_flag("LOCAL_ADMIN_ONLY", default=False)

    return RuntimeConfig(
        db_uri=db_uri,
        db_read_only=_env_flag("DB_READ_ONLY", default=False),
        auto_backup_before_write=_env_flag("AUTO_BACKUP_BEFORE_WRITE", default=False),
        auto_backup_keep=_env_int("AUTO_BACKUP_KEEP", default=DEFAULT_AUTO_BACKUP_KEEP),
        auto_backup_dir=Path(
            os.environ.get("AUTO_BACKUP_DIR", str(DEFAULT_BACKUP_DIR))
        ),
        enforce_backup_before_write=_env_flag(
            "ENFORCE_BACKUP_BEFORE_WRITE", default=False
        ),
        check_pending_migrations=_env_flag("CHECK_PENDING_MIGRATIONS", default=True),
        fail_on_pending_migrations=_env_flag(
            "FAIL_ON_PENDING_MIGRATIONS", default=False
        ),
        auto_create_db=_env_flag("AUTO_CREATE_DB", default=DEFAULT_AUTO_CREATE_DB),
        upload_folder=Path(os.environ.get("UPLOAD_FOLDER", str(DEFAULT_UPLOAD_FOLDER))),
        max_content_length=DEFAULT_MAX_CONTENT_LENGTH,
        allowed_extensions={"png", "jpg", "jpeg", "gif"},
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        gemini_model_name=os.environ.get(
            "GEMINI_MODEL_NAME", DEFAULT_GEMINI_MODEL_NAME
        ),
        gemini_max_output_tokens=_env_int(
            "GEMINI_MAX_OUTPUT_TOKENS", default=DEFAULT_GEMINI_MAX_OUTPUT_TOKENS
        ),
        classifier_cache_path=Path(
            os.environ.get("CLASSIFIER_CACHE_PATH", str(DEFAULT_CLASSIFIER_CACHE_PATH))
        ),
        data_cache_dir=Path(os.environ.get("DATA_CACHE_DIR", str(DEFAULT_CACHE_DIR))),
        reports_dir=Path(os.environ.get("REPORTS_DIR", str(DEFAULT_REPORTS_DIR))),
        local_admin_only=_env_flag("LOCAL_ADMIN_ONLY", default=False),
        cors_allowed_origins=os.environ.get(
            "CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS
        ),
    )


def _sqlite_uri(path: Path) -> str:
    """Convert a Path to SQLite URI."""
    return f"sqlite:///{path.resolve().as_posix()}"


__all__ = ["get_runtime_config", "_env_flag", "_env_int"]
