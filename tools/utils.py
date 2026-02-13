import json
import os
import time
from datetime import datetime

CONFIG_PATH = os.path.expanduser("~/clawd/research/config.json")
STATE_PATH = os.path.expanduser("~/clawd/research/state.json")
LOG_PATH = os.path.expanduser("~/clawd/research/research.log")

# Token/API cost tracking intentionally removed (2026-02-13).


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_state(path: str = STATE_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_state(updates: dict, path: str = STATE_PATH):
    state = load_state(path)
    state.update(updates)
    state["last_updated"] = time.time()
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def log(message: str, level: str = "INFO"):
    """Write log to file and print to stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")


def get_today_str():
    return datetime.now().strftime("%Y%m%d")
