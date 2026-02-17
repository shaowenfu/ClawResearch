#!/usr/bin/env python3
"""Generate Topics/INDEX.md (and include _archive summary).

Usage:
  python3 tools/index_topics.py

This is intentionally deterministic and safe to commit.
"""

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "Topics"
ARCHIVE = ROOT / "_archive"


def load_meta(topic_dir: Path):
    meta_path = topic_dir / "topic.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    lines = []
    lines.append(f"# Topics Index\n")
    lines.append(f"Generated: {datetime.now().isoformat()}\n")

    if not TOPICS.exists():
        lines.append("(Topics directory missing)\n")
    else:
        items = []
        for d in sorted(TOPICS.iterdir()):
            if not d.is_dir():
                continue
            meta = load_meta(d) or {}
            items.append(
                {
                    "slug": d.name,
                    "title": meta.get("title") or d.name,
                    "created_at": meta.get("created_at"),
                    "updated_at": meta.get("updated_at"),
                    "notion_page_id": meta.get("notion_page_id"),
                }
            )

        lines.append("## Active Topics\n")
        for it in items:
            lines.append(f"- **{it['slug']}** — {it['title']}\n")
            if it.get("notion_page_id"):
                lines.append(f"  - notion_page_id: `{it['notion_page_id']}`\n")
            if it.get("created_at"):
                lines.append(f"  - created_at: {it['created_at']}\n")
            if it.get("updated_at"):
                lines.append(f"  - updated_at: {it['updated_at']}\n")

    lines.append("\n## Archive\n")
    if not ARCHIVE.exists():
        lines.append("(no _archive directory)\n")
    else:
        # only summarize top-level
        for d in sorted(ARCHIVE.iterdir()):
            if d.is_dir():
                lines.append(f"- {d.name}/\n")

    out = TOPICS / "INDEX.md"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"wrote: {out}")


if __name__ == "__main__":
    main()
