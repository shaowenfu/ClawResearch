# InsightEngine Implementation Plan

## 1. Directory Structure
Target: `~/clawd/research/`

```
research/
├── config.json          # Config (Notion ID, etc.)
├── watchdog.py          # Background process to wake Shawn if stalled
├── state.json           # Global state of the current research task
├── tools/               # Helper scripts
│   ├── init_topic.py    # CLI to create new research folders
│   ├── notion_sync.py   # Script to update Notion DB
│   └── utils.py         # Shared logic
└── Topics/[YYYYMMDD_Topic]/    # Research Data (Created dynamically)
    ├── 00_Brief/
    ├── 01_RawMaterials/
    ├── 02_Distilled/
    ├── 03_Synthesis/
    └── report.md
```

## 2. Configuration (`config.json`)
Create this file with:
- `notion_database_id`: "3069db86-8c8b-807f-b049-d879e9bcf47b"
- `root_path`: "/home/admin/clawd/research"

## 3. Watchdog (`watchdog.py`)
A standalone Python script that runs in the background.
- **Logic**:
  - Load `state.json`.
  - Check `status` ("idle", "running", "paused").
  - Check `last_updated` timestamp.
  - If `status == "running"` AND `(now - last_updated) > 300` (5 mins):
    - Execute shell command: `moltbot cron wake --text "⚠️ Research Watchdog: Task stalled. Please resume."`
  - Sleep 60 seconds.
- **Resilience**: Should handle file read errors gracefully.

## 4. Helper Tools
### `tools/init_topic.py`
- Arguments: `topic_name`
- Action:
  - Create directory `YYYYMMDD_{topic_name}`.
  - Create subfolders (`00_Brief`, `01_RawMaterials`, etc.).
  - Initialize `state.json` in the topic folder (or update global state).
  - Print the path of the new workspace.

### `tools/notion_sync.py`
- Arguments: `topic_path`, `status` (optional), `report_file` (optional)
- Action:
  - Read `NOTION_KEY` from environment or config.
  - Update the Notion Database item corresponding to this topic.
  - If `report_file` is provided, read markdown and push as page content.

## 5. Execution Steps
1. Create `config.json`.
2. Implement `watchdog.py`.
3. Implement `tools/init_topic.py`.
4. Implement `tools/notion_sync.py` (Stub is fine, focus on structure).
5. Update `README.md` with usage instructions.
