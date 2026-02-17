import time
import json
import os
import subprocess
from datetime import datetime

STATE_FILE = os.path.expanduser("~/clawd/research/state.json")
LOCK_FILE = os.path.expanduser("~/clawd/research/watchdog.lock")
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

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_pid(path: str):
    try:
        with open(path, "r") as f:
            t = f.read().strip()
        return int(t) if t else None
    except Exception:
        return None


def main():
    # lock to prevent multiple watchdog instances; auto-clean stale lock
    if os.path.exists(LOCK_FILE):
        old_pid = _read_pid(LOCK_FILE)
        if old_pid and _pid_alive(old_pid):
            print(f"[{datetime.now()}] Watchdog lock exists (pid={old_pid}), refusing to start: {LOCK_FILE}")
            return
        # stale/corrupt lock
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        return

    print(f"[{datetime.now()}] Watchdog started. Monitoring {STATE_FILE}...")
    try:
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
    finally:
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass

if __name__ == "__main__":
    main()
