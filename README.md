# ClawResearch (InsightEngine)

[English] · [中文](./README.zh-CN.md)

A practical, file-based research workflow engine designed for long-running, tool-assisted investigations.

It provides:
- A **topic workspace layout** (raw materials → distilled notes → synthesis → final report)
- A **multi-step report pipeline** (outline → per-section drafting → final assembly)
- A **Notion delivery tool** that converts Markdown to Notion blocks (best-effort)
- A **task-level watchdog** to wake the agent when a run stalls (with cooldown + lock)

> Status: actively evolving. This repo is the public, reusable research engine (no private data).

## Quick Start

### 1) Configure
Edit `config.json`:
- `root_path`: workspace path (this repo directory)
- `notion_database_id`: target Notion database

Set env var:
- `NOTION_API_KEY` (Notion integration token)

### 2) Create a topic
```bash
python3 tools/init_topic.py "My Topic"
```
Then put sources into:
```
YYYYMMDD_My_Topic/01_RawMaterials/
```
(as `.md` files; web pages can be fetched and saved there)

### 3) Run the orchestrator (end-to-end)
```bash
python3 tools/orchestrator.py "My Topic"
```
This will:
- enforce a single-run lock
- start a watchdog (task-level)
- build outline → draft sections → assemble `report.md`
- deliver to Notion (overwrite mode)
- commit & push to `origin/main` (with retry)

## Repo Layout

```
.
├── tools/
│   ├── init_topic.py        # scaffold a topic workspace
│   ├── orchestrator.py      # run lock + watchdog + pipeline + delivery
│   ├── pipeline.py          # outline/sections/assemble (multi-step)
│   ├── notion_sync.py       # Markdown → Notion blocks + overwrite + retry
│   ├── moltbook_client.py   # Moltbook API helper (optional)
│   └── llm.py               # headless LLM runner (claude/gemini)
├── watchdog.py              # stall detector (cooldown + lock)
├── config.json              # local config (Notion DB id, root_path)
└── YYYYMMDD_TopicName/      # per-topic workspaces
    ├── 00_Brief/
    ├── 01_RawMaterials/
    ├── 02_Distilled/
    ├── 03_Synthesis/
    └── report.md
```

## Notes / Non-goals
- Notion does **not** render Markdown directly; we convert Markdown into Notion blocks.
- Markdown support is best-effort (headings/lists/code/quotes + some inline styles). Tables are currently degraded.
- This repo should not contain secrets. Put API keys in env/config outside git.

## License
MIT (if you want a different license, open an issue).
