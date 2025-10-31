"""
Lightweight JSON file cache for API responses.

Used for caching Google Distance Matrix results to reduce API calls.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional


_lock = threading.Lock()
_cache_path = Path("data/cache/distance_cache.json")


def _ensure_dir():
    _cache_path.parent.mkdir(parents=True, exist_ok=True)


def cache_get(key: str) -> Optional[Any]:
    _ensure_dir()
    if not _cache_path.exists():
        return None
    with _lock:
        try:
            with open(_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(key)
        except Exception:
            return None


def cache_set(key: str, value: Any) -> None:
    _ensure_dir()
    with _lock:
        try:
            if _cache_path.exists():
                with open(_cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
        except Exception:
            data = {}
        data[key] = value
        with open(_cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)


