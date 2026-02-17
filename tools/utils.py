import json
import os
import time
from datetime import datetime
from pathlib import Path

# Keep all paths consistent regardless of $HOME / working directory.
ROOT = Path(__file__).resolve().parents[1]  # .../research
CONFIG_PATH = str(ROOT / "config.json")
STATE_PATH = str(ROOT / "state.json")
LOG_PATH = str(ROOT / "research.log")

# Minimal stable schema for global state.json (avoid legacy fields causing confusion).
ALLOWED_STATE_KEYS = {
    "status",
    "step",
    "last_updated",
    "current_topic_path",
    "current_topic_name",
    "current_topic_slug",
    "watchdog_pid",
    "watchdog_last_alerted",
}


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _filter_state(d: dict) -> dict:
    if not isinstance(d, dict):
        return {}
    return {k: v for k, v in d.items() if k in ALLOWED_STATE_KEYS}


def load_state(path: str = STATE_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _filter_state(data)
    except json.JSONDecodeError:
        return {}


def save_state(updates: dict, path: str = STATE_PATH):
    state = load_state(path)
    state.update(_filter_state(updates))
    state["last_updated"] = time.time()
    state = _filter_state(state) | {"last_updated": state["last_updated"]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log(message: str, level: str = "INFO"):
    """Write log to file and print to stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")


def get_today_str():
    return datetime.now().strftime("%Y%m%d")
