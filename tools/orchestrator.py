import os
import argparse
import subprocess
import signal
import time
from pathlib import Path

from utils import load_state, save_state, log

ROOT = Path("/home/admin/clawd/research")
LOCK_PATH = ROOT / "run.lock"
WATCHDOG_SCRIPT = ROOT / "watchdog.py"


def _run(args, *, cwd=None, check=True):
    log(f"EXEC: {' '.join(str(a) for a in args)}")
    return subprocess.run(args, cwd=cwd, check=check)


def acquire_lock():
    if LOCK_PATH.exists():
        raise RuntimeError(f"Another run seems active (lock exists): {LOCK_PATH}")
    LOCK_PATH.write_text(str(os.getpid()))


def release_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def start_watchdog():
    # Start watchdog as child process (task-level), unbuffered
    p = subprocess.Popen(["python3", "-u", str(WATCHDOG_SCRIPT)])
    save_state({"watchdog_pid": p.pid})
    log(f"watchdog started pid={p.pid}")
    return p


def stop_watchdog(p: subprocess.Popen | None):
    if not p:
        return
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass
    log("watchdog stopped")


def heartbeat(step: str, *, status: str = "running"):
    save_state({"status": status, "step": step})


def init_topic(topic: str):
    init_script = ROOT / "tools" / "init_topic.py"
    _run(["python3", str(init_script), topic])
    state = load_state()
    return Path(state["current_topic_path"])


def run_delivery(topic_dir: Path, *, status: str):
    """Delivery step: Notion sync + git push with retries."""
    report = topic_dir / "report.md"

    # Notion delivery (retry handled inside notion_sync.py)
    heartbeat("delivery:notion")
    notion_sync = ROOT / "tools" / "notion_sync.py"
    _run(["python3", str(notion_sync), "--status", status, "--report", str(report)])

    # Git delivery with retry
    heartbeat("delivery:git")
    for attempt in range(4):
        try:
            _run(["git", "add", "-A"], cwd=str(ROOT))
            # commit may fail if nothing to commit
            subprocess.run(["git", "commit", "-m", f"deliver: {topic_dir.name}"], cwd=str(ROOT))
            _run(["git", "push", "origin", "main"], cwd=str(ROOT))
            return
        except Exception as e:
            log(f"git delivery failed attempt={attempt+1}: {e}", level="ERROR")
            time.sleep(1.2 * (2**attempt))
    raise RuntimeError("git delivery failed after retries")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="Research topic")
    args = parser.parse_args()

    acquire_lock()
    wd = None
    try:
        topic_dir = init_topic(args.topic)
        wd = start_watchdog()

        # NOTE: This orchestrator currently only enforces scaffolding + delivery.
        # Actual research steps are still manual/coding-agent driven.
        heartbeat("scaffolded")

        # Mark done only when report exists
        if not (topic_dir / "report.md").exists():
            raise RuntimeError("report.md missing; refusing to deliver")

        run_delivery(topic_dir, status="Done")
        heartbeat("done", status="done")
        log("✅ run complete")
    finally:
        stop_watchdog(wd)
        release_lock()


if __name__ == "__main__":
    main()
