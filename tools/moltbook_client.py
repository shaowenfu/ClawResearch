import json
import subprocess
import urllib.parse
from pathlib import Path

BASE = "https://www.moltbook.com/api/v1"


def _load_key():
    cred_path = Path.home() / ".config/moltbook/credentials.json"
    creds = json.loads(cred_path.read_text())
    return creds["api_key"]


def get_json(path: str):
    key = _load_key()
    url = f"{BASE}{path}"
    out = subprocess.check_output(["curl", "-s", url, "-H", f"Authorization: Bearer {key}"])
    return json.loads(out)


def search(q: str, *, type: str = "all", limit: int = 20):
    qs = urllib.parse.quote(q)
    return get_json(f"/search?q={qs}&type={urllib.parse.quote(type)}&limit={limit}")


def feed(sort: str = "hot", limit: int = 25):
    return get_json(f"/feed?sort={urllib.parse.quote(sort)}&limit={limit}")


def submolt_feed(name: str, sort: str = "new", limit: int = 25):
    name = urllib.parse.quote(name)
    return get_json(f"/submolts/{name}/feed?sort={urllib.parse.quote(sort)}&limit={limit}")
