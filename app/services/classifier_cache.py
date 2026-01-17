from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


def build_config_hash(config: Dict[str, object]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class ClassifierResultCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = Lock()
        self._loaded = False
        self._data: Dict[str, Dict[str, object]] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._data = {}
        self._loaded = True

    def get(self, question_id: int, config_hash: str, model_name: str) -> Optional[Dict[str, object]]:
        self._load()
        key = f"{question_id}:{config_hash}:{model_name}"
        return self._data.get(key)

    def set(self, question_id: int, config_hash: str, model_name: str, result: Dict[str, object]) -> None:
        self._load()
        key = f"{question_id}:{config_hash}:{model_name}"
        with self._lock:
            self._data[key] = {
                "result": result,
                "cached_at": datetime.utcnow().isoformat(),
            }

    def save(self) -> None:
        self._load()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, ensure_ascii=False, indent=2)
        temp_path.replace(self.path)
