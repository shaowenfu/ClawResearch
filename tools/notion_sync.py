import os
import argparse
import requests
import json
import re
import time
from datetime import datetime
from utils import load_config, load_state, save_state


def load_topic_meta(topic_dir: str):
    path = os.path.join(topic_dir, "topic.json")
    if not os.path.exists(path):
        return {}, path
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), path
    except Exception:
        return {}, path


def save_topic_meta(meta: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


NOTION_VERSION = "2022-06-28"
MAX_TEXT = 2000


def chunk_list(data, size=100):
    return [data[i : i + size] for i in range(0, len(data), size)]


def request_with_retry(method, url, *, headers=None, params=None, json_body=None, retries=4, backoff=0.6):
    """Small retry wrapper for transient 429/5xx."""
    last = None
    for i in range(retries + 1):
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json_body, timeout=12)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = resp
                sleep_s = backoff * (2**i)
                time.sleep(sleep_s)
                continue
            return resp
        except Exception as e:
            last = e
            time.sleep(backoff * (2**i))
    raise RuntimeError(f"request failed after retries: {method} {url} last={last}")


# ---------------- Markdown -> Notion Blocks ----------------

def _rt_plain(text):
    return {"type": "text", "text": {"content": text}}


def _rt(text, *, bold=False, italic=False, code=False, href=None):
    obj = {"type": "text", "text": {"content": text}}
    if href:
        obj["text"]["link"] = {"url": href}
    obj["annotations"] = {
        "bold": bool(bold),
        "italic": bool(italic),
        "strikethrough": False,
        "underline": False,
        "code": bool(code),
        "color": "default",
    }
    return obj


INLINE_RE = re.compile(
    r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^\)]+\))"
)


def parse_inline(text: str):
    """Best-effort inline parser: **bold**, *italic*, `code`, [txt](url)."""
    if not text:
        return []

    parts = INLINE_RE.split(text)
    out = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            out.append(_rt(part[2:-2], bold=True))
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            out.append(_rt(part[1:-1], italic=True))
        elif part.startswith("`") and part.endswith("`") and len(part) >= 2:
            out.append(_rt(part[1:-1], code=True))
        elif part.startswith("[") and "](" in part and part.endswith(")"):
            # [text](url)
            try:
                label = part[1 : part.index("](")]
                url = part[part.index("](") + 2 : -1]
                out.append(_rt(label, href=url))
            except Exception:
                out.append(_rt_plain(part))
        else:
            out.append(_rt_plain(part))

    # enforce notion MAX_TEXT across segments
    trimmed = []
    budget = MAX_TEXT
    for rt in out:
        s = rt["text"]["content"]
        if budget <= 0:
            break
        if len(s) > budget:
            rt = dict(rt)
            rt["text"] = dict(rt["text"])
            rt["text"]["content"] = s[:budget]
            trimmed.append(rt)
            budget = 0
        else:
            trimmed.append(rt)
            budget -= len(s)
    return trimmed


def markdown_to_blocks(md_text: str):
    """Simple markdown-to-blocks converter. Not full fidelity."""
    blocks = []
    lines = md_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")
        s = stripped.strip()

        if not s:
            i += 1
            continue

        # Code blocks
        if s.startswith("```"):
            language = s[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = "\n".join(code_lines)
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code[:MAX_TEXT]}}],
                        "language": language.split()[0],
                    },
                }
            )
            i += 1
            continue

        # headings
        if s.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": parse_inline(s[2:])}})
        elif s.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": parse_inline(s[3:])}})
        elif s.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": parse_inline(s[4:])}})

        # list items
        elif s.startswith("- ") or s.startswith("* "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": parse_inline(s[2:])},
                }
            )
        elif re.match(r"^\d+\. ", s):
            content = re.sub(r"^\d+\. ", "", s)
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": parse_inline(content)},
                }
            )

        # quote
        elif s.startswith("> "):
            blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": parse_inline(s[2:])}})

        # very rough table fallback: treat as paragraph
        else:
            # merge consecutive paragraph lines until blank
            para = [s]
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith(("#", "- ", "* ", "> ", "```")):
                para.append(lines[j].strip())
                j += 1
            text = " ".join(para)
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": parse_inline(text)}})
            i = j - 1

        i += 1

    return blocks


# ---------------- Notion Write ----------------

def clear_page_content(page_id, headers):
    """Delete all top-level blocks for overwrite mode.

    Note: Notion requires per-block deletes (no batch). We log progress to avoid "looks stuck".
    """
    blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    has_more = True
    next_cursor = None
    all_block_ids = []

    while has_more:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        resp = request_with_retry("GET", blocks_url, headers=headers, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch blocks: {resp.text}")
        data = resp.json()
        all_block_ids.extend([b["id"] for b in data.get("results", [])])
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    total = len(all_block_ids)
    if total == 0:
        return 0

    for idx, block_id in enumerate(all_block_ids, start=1):
        request_with_retry("DELETE", f"https://api.notion.com/v1/blocks/{block_id}", headers=headers)
        if idx % 10 == 0 or idx == total:
            print(f"… deleted {idx}/{total} blocks", flush=True)

    return total


def count_page_blocks(page_id, headers):
    blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    resp = request_with_retry("GET", blocks_url, headers=headers)
    if resp.status_code != 200:
        return None
    return len(resp.json().get("results", []))


def sync_notion(topic_path=None, status=None, report_file=None):
    config = load_config()
    database_id = config["notion_database_id"]
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        raise RuntimeError("NOTION_API_KEY not set")

    state = load_state()
    if not topic_path:
        topic_path = state.get("current_topic_path")

    # per-topic metadata (created/updated time + notion page id)
    topic_meta, topic_meta_path = load_topic_meta(topic_path)

    folder_name = os.path.basename(topic_path)
    topic_name = topic_meta.get("title") or (folder_name.split("_", 1)[1] if "_" in folder_name else folder_name)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # --- Preflight ---
    if report_file:
        if not os.path.exists(report_file):
            raise RuntimeError(f"report file not found: {report_file}")
        if os.path.getsize(report_file) < 200:
            raise RuntimeError(f"report too small (<200 bytes), refusing to deliver: {report_file}")

    # IMPORTANT: never fall back to global state notion_page_id.
    # Each topic must bind to its own Notion page via Topics/<slug>/topic.json.
    # Otherwise a new topic run could overwrite a previous report.
    page_id = topic_meta.get("notion_page_id")

    # 1) Create or update metadata
    if not page_id:
        now_iso = datetime.now().isoformat()
        created_at = topic_meta.get("created_at") or now_iso

        data = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": topic_name}}]},
                "Status": {"select": {"name": status or "To Do"}},
                "Last Updated": {"date": {"start": now_iso}},
                "Updated At": {"date": {"start": now_iso}},
                "Created At": {"date": {"start": created_at}},
            },
        }
        resp = request_with_retry("POST", "https://api.notion.com/v1/pages", headers=headers, json_body=data)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to create page: {resp.text}")
        page_id = resp.json()["id"]
        # store notion page id per-topic to avoid cross-topic collisions
        topic_meta["notion_page_id"] = page_id
        save_topic_meta(topic_meta, topic_meta_path)
        # NOTE: we intentionally do NOT store page_id in global state.
        # Global state is shared across runs and could cause cross-topic overwrites.
    else:
        now_iso = datetime.now().isoformat()
        props = {
            "Last Updated": {"date": {"start": now_iso}},
            "Updated At": {"date": {"start": now_iso}},
            # keep title in sync (also fixes cases where a page was accidentally reused)
            "Name": {"title": [{"text": {"content": topic_name}}]},
        }
        if status:
            props["Status"] = {"select": {"name": status}}
        request_with_retry(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=headers,
            json_body={"properties": props},
        )

    # Ensure per-topic meta always records the current page id (even if page existed)
    if page_id and topic_meta.get("notion_page_id") != page_id:
        topic_meta["notion_page_id"] = page_id
        if not topic_meta.get("created_at"):
            topic_meta["created_at"] = datetime.now().isoformat()
        topic_meta["updated_at"] = datetime.now().isoformat()
        save_topic_meta(topic_meta, topic_meta_path)

    # 2) Overwrite content
    if report_file:
        print(f"🧹 clearing page content... page_id={page_id}", flush=True)
        cleared = clear_page_content(page_id, headers)
        print(f"✨ cleared blocks={cleared}", flush=True)

        with open(report_file, "r", encoding="utf-8") as f:
            md = f.read()
        blocks = markdown_to_blocks(md)
        if not blocks:
            raise RuntimeError("no blocks generated from report")

        chunks = chunk_list(blocks, 100)
        for idx, chunk in enumerate(chunks, start=1):
            print(f"⬆️ uploading chunk {idx}/{len(chunks)} blocks={len(chunk)}", flush=True)
            resp = request_with_retry(
                "PATCH",
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=headers,
                json_body={"children": chunk},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"failed to upload chunk: {resp.text}")

        # Postflight verify
        n = count_page_blocks(page_id, headers)
        if n is None or n == 0:
            raise RuntimeError("postflight failed: page has 0 blocks")

        # update topic meta timestamps
        topic_meta["updated_at"] = datetime.now().isoformat()
        if not topic_meta.get("created_at"):
            topic_meta["created_at"] = topic_meta["updated_at"]
        save_topic_meta(topic_meta, topic_meta_path)

        print(f"✅ Notion delivery complete. page_id={page_id} cleared={cleared} blocks_now={n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="Path to topic folder")
    parser.add_argument("--status", help="Status to set")
    parser.add_argument("--report", help="Path to report markdown file")
    args = parser.parse_args()

    sync_notion(args.path, args.status, args.report)
