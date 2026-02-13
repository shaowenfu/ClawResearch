import time
import json
import os
import subprocess
from datetime import datetime

STATE_FILE = os.path.expanduser("~/clawd/research/state.json")
CHECK_INTERVAL = 60  # seconds
STALL_THRESHOLD = 300  # 5 minutes

def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def wake_moltbot(message):
    try:
        cmd = ["moltbot", "cron", "wake", "--text", message, "--mode", "now"]
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
            last_updated = state.get("last_updated", 0)
            now = time.time()
            
            if status == "running":
                time_since_update = now - last_updated
                if time_since_update > STALL_THRESHOLD:
                    msg = f"⚠️ Research Watchdog: Task stalled for {int(time_since_update)}s. Please resume."
                    wake_moltbot(msg)
                    # Optional: Update state to 'alerted' to avoid spamming? 
                    # For now, we'll rely on the fact that waking Moltbot usually triggers action.
                    # Or we could sleep longer.
                    time.sleep(300) # Sleep 5 mins after alerting to avoid spam
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
