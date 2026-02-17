import os
import argparse
import subprocess
import signal
import time
from pathlib import Path

from utils import load_state, save_state, log
from pipeline import build_outline, write_section, assemble_report

ROOT = Path(__file__).resolve().parents[1]  # .../research
LOCK_PATH = ROOT / "run.lock"
WATCHDOG_LOCK_PATH = ROOT / "watchdog.lock"
WATCHDOG_SCRIPT = ROOT / "watchdog.py"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # If we can't signal it, assume alive.
        return True


def _run(args, *, cwd=None, check=True):
    log(f"EXEC: {' '.join(str(a) for a in args)}")
    return subprocess.run(args, cwd=cwd, check=check)


def acquire_lock():
    # Stale lock protection: if lock exists but PID is not alive, clear it.
    if LOCK_PATH.exists():
        try:
            pid_txt = LOCK_PATH.read_text().strip()
            pid = int(pid_txt) if pid_txt else None
        except Exception:
            pid = None

        if pid and _pid_alive(pid):
            raise RuntimeError(f"Another run seems active (lock exists pid={pid}): {LOCK_PATH}")

        # stale lock
        try:
            LOCK_PATH.unlink()
        except Exception:
            pass

    LOCK_PATH.write_text(str(os.getpid()))


def release_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def start_watchdog():
    # Start watchdog as child process (task-level), unbuffered.
    # If a stale watchdog.lock exists (e.g., previous crash), clear it first.
    if WATCHDOG_LOCK_PATH.exists():
        try:
            pid_txt = WATCHDOG_LOCK_PATH.read_text().strip()
            pid = int(pid_txt) if pid_txt else None
        except Exception:
            pid = None
        if not (pid and _pid_alive(pid)):
            try:
                WATCHDOG_LOCK_PATH.unlink()
            except Exception:
                pass

    p = subprocess.Popen(["python3", "-u", str(WATCHDOG_SCRIPT)])
    save_state({"watchdog_pid": p.pid})
    log(f"watchdog started pid={p.pid}")
    return p


from typing import Optional

def stop_watchdog(p: Optional[subprocess.Popen]):
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
    _run(["python3", str(notion_sync), "--path", str(topic_dir), "--status", status, "--report", str(report)])

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

        heartbeat("scaffolded")

        # --- Research pipeline (multi-step, non-one-shot) ---
        # Expect user to populate 01_RawMaterials beforehand for many topics.
        # For topics that already have materials, we proceed.
        raw_dir = topic_dir / "01_RawMaterials"
        if not raw_dir.exists() or not list(raw_dir.glob("*.md")):
            raise RuntimeError("01_RawMaterials is empty; add sources before running orchestrator")

        outline = build_outline(args.topic, topic_dir)

        # Derive section titles from outline headings (very simple heuristic)
        section_titles = []
        for line in outline.splitlines():
            s = line.strip()
            if s.startswith("## "):
                section_titles.append(s[3:].strip())
        # fallback
        if not section_titles:
            section_titles = ["协议与机制", "技术实现与合约", "生态与市场", "风险与争议", "机会与行动建议"]

        for title in section_titles[:6]:
            write_section(args.topic, topic_dir, title, outline)

        assemble_report(args.topic, topic_dir)

        run_delivery(topic_dir, status="Done")
        heartbeat("done", status="done")
        log("✅ run complete")
    finally:
        stop_watchdog(wd)
        release_lock()


if __name__ == "__main__":
    main()
