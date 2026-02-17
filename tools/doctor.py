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

ROOT = Path(__file__).resolve().parents[1]  # .../research
STATE = ROOT / "state.json"
RUN_LOCK = ROOT / "run.lock"
WATCHDOG_LOCK = ROOT / "watchdog.lock"
TOPICS = ROOT / "Topics"

# Derived artifact dirs (safe to delete/regenerate)
SPILL_DIR = Path("00_Brief/_spill")
PROMPTS_DIR = Path("00_Brief/_prompts")
RAW_SUMMARY_DIR = Path("02_Distilled/_raw_chunk_summaries")

# Heuristics / thresholds
MAX_SPILL_TOTAL_BYTES = 25 * 1024 * 1024  # 25MB per topic is suspicious
MAX_CHUNKS_WARN = 80


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


def _dir_size_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for f in p.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except Exception:
                pass
    return total


def scan_artifacts(limit: int = 50):
    """Check spill/distill artifacts integrity.

    Safe, derived artifacts:
    - 00_Brief/_spill/raw_chunk_*.md
    - 02_Distilled/_raw_chunk_summaries/summary_raw_chunk_*.md
    - 00_Brief/_prompts/*.txt

    We report:
    - missing directories when other derived dirs exist
    - chunk/summaries count mismatch
    - spill too large
    - suspiciously high chunk count
    """
    issues = []
    if not TOPICS.exists():
        return issues

    for i, topic_dir in enumerate(sorted(TOPICS.iterdir())):
        if i >= limit:
            break
        if not topic_dir.is_dir():
            continue

        raw_dir = topic_dir / "01_RawMaterials"
        has_raw = raw_dir.exists() and any(raw_dir.glob("*.md"))

        spill = topic_dir / SPILL_DIR
        prompts = topic_dir / PROMPTS_DIR
        summaries = topic_dir / RAW_SUMMARY_DIR

        spill_chunks = sorted(spill.glob("raw_chunk_*.md")) if spill.exists() else []
        summary_files = sorted(summaries.glob("summary_raw_chunk_*.md")) if summaries.exists() else []

        # Orphan artifacts: derived dirs exist but no raw materials.
        if not has_raw and (spill.exists() or summaries.exists()):
            issues.append(("artifact_orphan_without_raw", {"topic": str(topic_dir)}))

        # If raw exists but spill missing: not an error (it will be created on next run).
        # But if summaries exist without spill, that's inconsistent.
        if summaries.exists() and not spill.exists():
            issues.append(("artifact_missing_spill_dir", {"topic": str(topic_dir)}))

        # If spill exists, check size & chunk count
        if spill.exists():
            total_bytes = _dir_size_bytes(spill)
            if total_bytes > MAX_SPILL_TOTAL_BYTES:
                issues.append(("spill_too_large", {"topic": str(topic_dir), "bytes": total_bytes}))
            if len(spill_chunks) > MAX_CHUNKS_WARN:
                issues.append(("spill_chunk_count_high", {"topic": str(topic_dir), "chunks": len(spill_chunks)}))

        # chunk/summaries mismatch
        if spill_chunks or summary_files:
            chunk_stems = {p.stem for p in spill_chunks}
            summary_stems = {p.name.replace("summary_", "").rsplit(".", 1)[0] for p in summary_files}

            if spill_chunks and summaries.exists() and len(summary_files) != len(spill_chunks):
                issues.append(
                    (
                        "spill_summary_count_mismatch",
                        {"topic": str(topic_dir), "chunks": len(spill_chunks), "summaries": len(summary_files)},
                    )
                )

            # even if counts match, ensure stems correspond (detect stray summaries)
            if summary_stems and chunk_stems and summary_stems != chunk_stems:
                missing = sorted(chunk_stems - summary_stems)
                extra = sorted(summary_stems - chunk_stems)
                issues.append(
                    (
                        "spill_summary_stem_mismatch",
                        {"topic": str(topic_dir), "missing": missing, "extra": extra},
                    )
                )

        # prompts directory sanity
        if prompts.exists() and not prompts.is_dir():
            issues.append(("artifact_prompts_not_dir", {"topic": str(topic_dir)}))

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


def _safe_to_fix_artifacts() -> bool:
    """Only fix derived artifacts when no active run.lock PID."""
    if RUN_LOCK.exists():
        pid = read_pid(RUN_LOCK)
        if pid and pid_alive(pid):
            return False
    return True


def _rm_tree(p: Path):
    if not p.exists():
        return
    # conservative delete: only within repo
    if ROOT not in p.resolve().parents and p.resolve() != ROOT:
        raise RuntimeError(f"refusing to delete outside repo: {p}")
    for child in sorted(p.rglob("*"), reverse=True):
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        except Exception:
            pass
    try:
        if p.exists() and p.is_dir():
            p.rmdir()
    except Exception:
        pass


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
            if RUN_LOCK.exists():
                pid = read_pid(RUN_LOCK)
                if pid and pid_alive(pid):
                    log(f"state says running but run.lock pid={pid} alive; not changing state", level="WARN")
                    continue
            save_state({"status": "idle", "step": "doctor:reset_to_idle"}, path=str(STATE))
            fixed.append(kind)

        # Derived artifact fixes (safe delete + regenerate on next run)
        if kind in (
            "artifact_orphan_without_raw",
            "artifact_missing_spill_dir",
            "spill_too_large",
            "spill_chunk_count_high",
            "spill_summary_count_mismatch",
            "spill_summary_stem_mismatch",
            "artifact_prompts_not_dir",
        ):
            if not _safe_to_fix_artifacts():
                log("Active run.lock detected; skipping artifact fixes", level="WARN")
                continue

            topic = payload.get("topic") if isinstance(payload, dict) else None
            if not topic:
                continue
            topic_dir = Path(topic)
            # only allow Topics/*
            try:
                topic_dir.resolve().relative_to(TOPICS.resolve())
            except Exception:
                log(f"refusing artifact fix outside Topics: {topic_dir}", level="WARN")
                continue

            # Delete derived dirs conservatively.
            for rel in (SPILL_DIR, RAW_SUMMARY_DIR, PROMPTS_DIR):
                _rm_tree(topic_dir / rel)
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
    artifact_issues = scan_artifacts()
    notion_issues = scan_notion_collisions()

    all_issues = (
        [("lock", x) for x in lock_issues]
        + [("state", x) for x in state_issues]
        + [("topic", x) for x in topic_issues]
        + [("artifact", x) for x in artifact_issues]
        + [("notion", x) for x in notion_issues]
    )

    if not all_issues:
        log("doctor: no issues found")
        return

    log("doctor: issues found:")
    for scope, (kind, payload) in all_issues:
        log(f"- [{scope}] {kind} {payload}")

    if args.fix:
        fixed = fix(lock_issues + state_issues + artifact_issues)
        log(f"doctor: fixed={fixed}")


if __name__ == "__main__":
    main()
