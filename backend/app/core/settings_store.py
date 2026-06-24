"""
Persistent key-value settings backed by a JSON file in the data directory.
Thread-safe; uses an atomic write (temp-file rename) to prevent corruption.
"""
import json
import threading
from pathlib import Path

from app.core.config import DATA_DIR

_SETTINGS_FILE = DATA_DIR / "settings.json"
_lock = threading.Lock()

DEFAULTS: dict = {
    "zim_scan_path": "",
}


def load() -> dict:
    with _lock:
        try:
            if _SETTINGS_FILE.exists():
                return {**DEFAULTS, **json.loads(_SETTINGS_FILE.read_text("utf-8"))}
        except Exception:
            pass
        return dict(DEFAULTS)


def save(data: dict) -> dict:
    merged = {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
    with _lock:
        tmp = _SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(merged, indent=2), "utf-8")
        tmp.replace(_SETTINGS_FILE)
    return merged


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> dict:
    data = load()
    data[key] = value
    return save(data)
