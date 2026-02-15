import os
import re
import json
import argparse
from datetime import datetime, timezone

from utils import load_config, save_state, log


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    """Stable slug for directory naming (same topic -> same folder).

    Prefer readable slugs for ASCII names; for non-ASCII (e.g., Chinese), fall back
    to a stable hash-based slug to avoid collisions like "topic".

    Rules (ASCII path):
    - lowercase
    - keep a-z0-9
    - convert spaces/punct to '-'
    - collapse repeats

    Fallback (non-ASCII):
    - t<YYYYMMDD>-<8hex> where hex is md5(utf-8 name)
    """
    raw = name.strip()
    s = raw.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if s:
        return s

    import hashlib
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    day = datetime.now().strftime("%Y%m%d")
    return f"t{day}-{h}"


def ensure_dirs(topic_dir: str):
    subdirs = ["00_Brief", "01_RawMaterials", "02_Distilled", "03_Synthesis"]
    for d in subdirs:
        os.makedirs(os.path.join(topic_dir, d), exist_ok=True)


def init_topic(topic_name: str):
    log(f"Initializing topic: {topic_name}")

    config = load_config()
    root_path = config["root_path"]
    topics_root = os.path.join(root_path, "Topics")
    os.makedirs(topics_root, exist_ok=True)

    slug = slugify(topic_name)
    topic_dir = os.path.join(topics_root, slug)
    meta_path = os.path.join(topic_dir, "topic.json")

    is_new = not os.path.exists(topic_dir)
    os.makedirs(topic_dir, exist_ok=True)
    ensure_dirs(topic_dir)

    # Create report file only if missing (do not overwrite on re-runs)
    report_path = os.path.join(topic_dir, "report.md")
    if not os.path.exists(report_path):
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Research Report: {topic_name}\n\n## Status\nInitialized\n")

    # Load or create meta
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}

    created_at = meta.get("created_at") or now_iso()
    updated_at = now_iso()

    meta.update(
        {
            "title": topic_name,
            "slug": slug,
            "created_at": created_at,
            "updated_at": updated_at,
            # notion_page_id is stored per-topic to avoid cross-topic collisions
            "notion_page_id": meta.get("notion_page_id"),
        }
    )

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    log(f"Workspace ready: {topic_dir} (new={is_new})")

    # Update GLOBAL run state (not per-topic metadata)
    save_state(
        {
            "status": "running",
            "step": "initialized",
            "current_topic_path": topic_dir,
            "current_topic_name": topic_name,
            "current_topic_slug": slug,
        }
    )

    return topic_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="Research topic name")
    args = parser.parse_args()
    init_topic(args.topic)
