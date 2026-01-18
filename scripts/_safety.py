"""
Script safety helpers for destructive operations.

Provides SafetyLevel enum and require_confirmation() function.
"""

import os
import sys
from enum import Enum
from typing import Optional, Callable, Any


class SafetyLevel(Enum):
    """Standard safety levels for scripts."""

    READ_ONLY = "READ_ONLY"
    MUTATES_STATE = "MUTATES_STATE"
    DESTRUCTIVE = "DESTRUCTIVE"


def require_confirmation(
    level: SafetyLevel,
    message: str,
    env_flag: Optional[str] = None,
    cli_flag: Optional[bool] = False,
    dry_run: bool = False,
) -> bool:
    """
    Check if destructive operation is allowed.

    Args:
        level: Safety level of the operation
        message: Description of what will be modified
        env_flag: Environment variable name to check (e.g., "ALLOW_DESTRUCTIVE")
        cli_flag: Whether --yes-i-really-mean-it was passed
        dry_run: Whether dry-run mode is enabled

    Returns:
        True if operation should proceed, False otherwise
    """
    if dry_run:
        print(f"[DRY-RUN] Would {message}")
        return False

    if level != SafetyLevel.DESTRUCTIVE:
        return True

    env_allowed = False
    if env_flag:
        env_value = os.environ.get(env_flag)
        env_allowed = env_value and env_value.lower() in ("1", "true", "yes", "on")

    if env_allowed or cli_flag:
        print(f"[CONFIRMED] {message}")
        return True

    print(f"[BLOCKED] Destructive operation requires confirmation.")
    print(f"  Message: {message}")
    if env_flag:
        print(f"  Env var option: {env_flag}=1")
    print(f"  CLI option: --yes-i-really-mean-it")
    return False


def print_script_header(script_name: str, target_db: Optional[str] = None) -> None:
    """
    Print standardized script header with timestamp and target info.

    Args:
        script_name: Name of the script being run
        target_db: Target database path (if applicable)
    """
    from datetime import datetime

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{script_name}] Started at {timestamp}")
    if target_db:
        print(f"[{script_name}] Target DB: {target_db}")


__all__ = ["SafetyLevel", "require_confirmation", "print_script_header"]
