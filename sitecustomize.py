from __future__ import annotations

import os
import sys
from pathlib import Path


def _using_project_venv() -> bool:
    repo_root = Path(__file__).resolve().parent
    expected = (repo_root / ".venv").resolve()
    try:
        prefix = Path(sys.prefix).resolve()
    except Exception:
        return False
    return prefix == expected


def _skip_check() -> bool:
    value = os.environ.get("ALLOW_OUTSIDE_VENV")
    return bool(value) and value.lower() in ("1", "true", "yes", "on")


if not _using_project_venv() and not _skip_check():
    sys.stderr.write(
        "This project requires the local .venv.\n"
        "Activate it with: .venv\\Scripts\\activate\n"
        "To bypass, set ALLOW_OUTSIDE_VENV=1.\n"
    )
    raise SystemExit(1)
