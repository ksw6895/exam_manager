"""Configuration package with layered settings.

Provides a centralized `get_config()` function that returns an AppConfig singleton.
"""

import threading

from .base import DEFAULT_SECRET_KEY
from .runtime import get_runtime_config
from .experiment import get_experiment_config
from .schema import AppConfig, RuntimeConfig, ExperimentConfig

# Singleton cache
_config_cache = None
_config_lock = threading.Lock()
_config_name = "default"  # Flask profile name


def set_config_name(name: str) -> None:
    """
    Set the Flask config profile name.

    This must be called before `get_config()` if using a non-default profile.
    """
    global _config_name
    with _config_lock:
        _config_name = name
        _config_cache = None  # Invalidate cache


def get_config() -> AppConfig:
    """
    Get the application configuration (singleton).

    Returns:
        AppConfig instance with runtime and experiment settings
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    with _config_lock:
        if _config_cache is None:
            runtime = get_runtime_config(flask_config_name=_config_name)
            experiment = get_experiment_config()
            _config_cache = AppConfig(
                runtime=runtime,
                experiment=experiment,
                secret_key=DEFAULT_SECRET_KEY,
            )

    return _config_cache


__all__ = [
    "get_config",
    "set_config_name",
    "RuntimeConfig",
    "ExperimentConfig",
    "AppConfig",
]
