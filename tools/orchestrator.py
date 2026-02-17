import os
import argparse
import subprocess
import signal
import time
import json
import socket
import platform
import traceback
from pathlib import Path
from datetime import datetime, timezone

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


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _git_head(root: Path):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="Research topic")
    parser.add_argument("--sections", type=int, default=6, help="Max sections to draft")
    args = parser.parse_args()

    acquire_lock()
    wd = None
    topic_dir = None

    # run meta: written to disk for post-mortem even if process gets killed.
    run_meta = {
        "run_id": f"run_{int(time.time())}_{os.getpid()}",
        "topic": args.topic,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "started_at": _now_iso(),
        "repo_head": _git_head(ROOT),
        "status": "running",
        "phases": [],
    }

    def write_meta():
        nonlocal run_meta, topic_dir
        if not topic_dir:
            return
        try:
            p = topic_dir / "00_Brief" / "run_meta.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def phase(name: str, **extra):
        run_meta["phases"].append({"name": name, "at": _now_iso(), **extra})
        write_meta()

    try:
        phase("init_topic:begin")
        topic_dir = init_topic(args.topic)
        phase("init_topic:done", topic_dir=str(topic_dir))

        wd = start_watchdog()
        phase("watchdog:started", watchdog_pid=getattr(wd, "pid", None))

        heartbeat("scaffolded")
        phase("preflight")

        # --- Research pipeline (multi-step, non-one-shot) ---
        raw_dir = topic_dir / "01_RawMaterials"
        if not raw_dir.exists() or not list(raw_dir.glob("*.md")):
            raise RuntimeError("01_RawMaterials is empty; add sources before running orchestrator")

        phase("outline:begin")
        outline = build_outline(args.topic, topic_dir)
        phase("outline:done", outline_bytes=len(outline or ""))

        # Derive section titles from outline headings (very simple heuristic)
        section_titles = []
        for line in outline.splitlines():
            s = line.strip()
            if s.startswith("## "):
                section_titles.append(s[3:].strip())
        if not section_titles:
            section_titles = ["协议与机制", "技术实现与合约", "生态与市场", "风险与争议", "机会与行动建议"]

        phase("sections:begin", planned=min(args.sections, len(section_titles)))
        for idx, title in enumerate(section_titles[: args.sections], start=1):
            phase("section:begin", index=idx, title=title)
            write_section(args.topic, topic_dir, title, outline)
            phase("section:done", index=idx, title=title)
        phase("sections:done")

        phase("assemble:begin")
        report = assemble_report(args.topic, topic_dir)
        phase("assemble:done", report_bytes=len(report or ""))

        phase("delivery:begin")
        run_delivery(topic_dir, status="Done")
        phase("delivery:done")

        heartbeat("done", status="done")
        run_meta["status"] = "done"
        run_meta["finished_at"] = _now_iso()
        write_meta()
        log("✅ run complete")

    except Exception as e:
        # Persist error info for post-mortem.
        run_meta["status"] = "error"
        run_meta["finished_at"] = _now_iso()
        run_meta["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        write_meta()
        # Ensure global state isn't left as running.
        heartbeat(f"error:{type(e).__name__}", status="idle")
        raise

    finally:
        stop_watchdog(wd)
        release_lock()


if __name__ == "__main__":
    main()
