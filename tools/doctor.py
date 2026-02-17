#!/usr/bin/env python3
"""ClawResearch doctor: scan + (optional) fix stale state/locks.

Usage:
  python3 tools/doctor.py --scan
  python3 tools/doctor.py --fix

What it checks:
- run.lock / watchdog.lock stale PID cleanup
- state.json 'running' but no active PID + old last_updated
- topic workspace sanity (missing dirs, empty RawMaterials)
- notion_page_id collisions across Topics/*/topic.json (overwrite risk)

This is deliberately conservative: it only auto-fixes obviously-stale locks.
"""

import argparse
import os
import time
from pathlib import Path

from utils import load_state, save_state, log

import json

ROOT = Path("/home/admin/clawd/research")
STATE = ROOT / "state.json"
RUN_LOCK = ROOT / "run.lock"
WATCHDOG_LOCK = ROOT / "watchdog.lock"
TOPICS = ROOT / "Topics"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_pid(p: Path):
    try:
        txt = p.read_text().strip()
        return int(txt) if txt else None
    except Exception:
        return None


def scan_locks():
    issues = []

    if RUN_LOCK.exists():
        pid = read_pid(RUN_LOCK)
        if pid and not pid_alive(pid):
            issues.append(("stale_run_lock", pid))
        elif pid is None:
            issues.append(("corrupt_run_lock", None))

    if WATCHDOG_LOCK.exists():
        pid = read_pid(WATCHDOG_LOCK)
        if pid and not pid_alive(pid):
            issues.append(("stale_watchdog_lock", pid))
        elif pid is None:
            issues.append(("corrupt_watchdog_lock", None))

    return issues


def scan_state():
    state = load_state(str(STATE)) if STATE.exists() else {}
    if not state:
        return []

    issues = []
    status = state.get("status")
    last_updated = float(state.get("last_updated", 0) or 0)
    age = time.time() - last_updated if last_updated else None

    # Heuristic: running + older than 30min is suspicious.
    if status == "running" and age is not None and age > 1800:
        wd_pid = state.get("watchdog_pid")
        if isinstance(wd_pid, int) and not pid_alive(wd_pid):
            issues.append(("running_but_watchdog_dead", {"age_sec": int(age), "watchdog_pid": wd_pid}))
        else:
            issues.append(("running_stale", {"age_sec": int(age)}))

    return issues


def scan_topics(limit: int = 50):
    issues = []
    if not TOPICS.exists():
        return [("topics_missing", str(TOPICS))]

    for i, topic_dir in enumerate(sorted(TOPICS.iterdir())):
        if i >= limit:
            break
        if not topic_dir.is_dir():
            continue
        raw = topic_dir / "01_RawMaterials"
        if raw.exists() and raw.is_dir():
            if not list(raw.glob("*.md")):
                issues.append(("rawmaterials_empty", str(topic_dir)))
        else:
            issues.append(("rawmaterials_missing", str(topic_dir)))

    return issues


def scan_notion_collisions():
    """Detect notion_page_id reused across topics (overwrite risk)."""
    issues = []
    if not TOPICS.exists():
        return issues

    pages = {}
    for topic_dir in TOPICS.iterdir():
        if not topic_dir.is_dir():
            continue
        meta = topic_dir / "topic.json"
        if not meta.exists():
            continue
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        pid = d.get("notion_page_id")
        if pid:
            pages.setdefault(pid, []).append(str(topic_dir))

    for pid, dirs in pages.items():
        if len(dirs) > 1:
            issues.append(("notion_page_id_collision", {"page_id": pid, "topics": dirs}))

    return issues


def fix(issues):
    fixed = []
    for kind, payload in issues:
        if kind in ("stale_run_lock", "corrupt_run_lock") and RUN_LOCK.exists():
            try:
                RUN_LOCK.unlink()
                fixed.append(kind)
            except Exception as e:
                log(f"Failed to remove {RUN_LOCK}: {e}", level="ERROR")

        if kind in ("stale_watchdog_lock", "corrupt_watchdog_lock") and WATCHDOG_LOCK.exists():
            try:
                WATCHDOG_LOCK.unlink()
                fixed.append(kind)
            except Exception as e:
                log(f"Failed to remove {WATCHDOG_LOCK}: {e}", level="ERROR")

        if kind in ("running_but_watchdog_dead", "running_stale"):
            # Only set idle if there is no active run.lock PID.
            if RUN_LOCK.exists():
                pid = read_pid(RUN_LOCK)
                if pid and pid_alive(pid):
                    log(f"state says running but run.lock pid={pid} alive; not changing state", level="WARN")
                    continue
            save_state({"status": "idle", "step": "doctor:reset_to_idle"}, path=str(STATE))
            fixed.append(kind)

    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    if not (args.scan or args.fix):
        args.scan = True

    lock_issues = scan_locks()
    state_issues = scan_state()
    topic_issues = scan_topics()
    notion_issues = scan_notion_collisions()

    all_issues = [("lock", x) for x in lock_issues] + [("state", x) for x in state_issues] + [("topic", x) for x in topic_issues] + [("notion", x) for x in notion_issues]

    if not all_issues:
        log("doctor: no issues found")
        return

    log("doctor: issues found:")
    for scope, (kind, payload) in all_issues:
        log(f"- [{scope}] {kind} {payload}")

    if args.fix:
        fixed = fix(lock_issues + state_issues)
        log(f"doctor: fixed={fixed}")


if __name__ == "__main__":
    main()
