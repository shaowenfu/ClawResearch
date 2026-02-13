import time
import json
import os
import subprocess
from datetime import datetime

STATE_FILE = os.path.expanduser("~/clawd/research/state.json")
CHECK_INTERVAL = 60  # seconds
STALL_THRESHOLD = 300  # seconds (5 minutes)

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_state(state: dict):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[{datetime.now()}] Failed to save state: {e}")

def wake_moltbot(message):
    try:
        # Use system event CLI command which is correct for waking the bot
        cmd = ["moltbot", "system", "event", "--text", message, "--mode", "now"]
        subprocess.run(cmd, check=True)
        print(f"[{datetime.now()}] Woke Moltbot: {message}")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to wake Moltbot: {e}")

def main():
    print(f"[{datetime.now()}] Watchdog started. Monitoring {STATE_FILE}...")
    while True:
        state = load_state()
        if state:
            status = state.get("status")
            last_updated = float(state.get("last_updated", 0) or 0)
            now = time.time()

            if status == "running":
                time_since_update = now - last_updated

                # Cooldown to avoid spam: only alert at most once per 10 minutes
                last_alerted = float(state.get("watchdog_last_alerted", 0) or 0)
                cooldown = 600

                if time_since_update > STALL_THRESHOLD and (now - last_alerted) > cooldown:
                    msg = f"⚠️ Research Watchdog: Task stalled for {int(time_since_update)}s. Please resume."
                    wake_moltbot(msg)
                    state["watchdog_last_alerted"] = now
                    save_state(state)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
