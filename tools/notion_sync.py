import os
import argparse
import requests
import json
from datetime import datetime
from utils import load_config, load_state, save_state

def sync_notion(topic_path=None, status=None, report_file=None):
    config = load_config()
    database_id = config["notion_database_id"]
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print("⚠️  Warning: NOTION_API_KEY not set. Skipping sync.")
        return

    # If topic path not provided, assume current
    if not topic_path:
        state = load_state()
        topic_path = state.get("current_topic_path")
        if not topic_path:
            print("❌ No topic path provided or found in state.")
            return

    # Extract topic name from path if needed (e.g. YYYYMMDD_Name -> Name)
    folder_name = os.path.basename(topic_path)
    # Assume folder format YYYYMMDD_Topic
    if "_" in folder_name:
        topic_name = folder_name.split("_", 1)[1]
    else:
        topic_name = folder_name

    # Check if page exists for this topic (simple search by title)
    # For now, we'll just create or update the *latest* entry matching the title if possible,
    # or just create a new one if we can't easily find it without storing the page_id.
    # To be robust, we should store page_id in state.json.
    state = load_state()
    page_id = state.get("notion_page_id")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    if not page_id:
        # Create new page
        data = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": topic_name}}]},
                "Status": {"select": {"name": status or "To Do"}},
                "Last Updated": {"date": {"start": datetime.now().isoformat()}}
            }
        }
        resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
        if resp.status_code == 200:
            new_page = resp.json()
            page_id = new_page["id"]
            save_state({"notion_page_id": page_id})
            print(f"✅ Created Notion page: {page_id}")
        else:
            print(f"❌ Failed to create Notion page: {resp.text}")
            return
    else:
        # Update existing page
        props = {}
        if status:
            props["Status"] = {"select": {"name": status}}
        
        props["Last Updated"] = {"date": {"start": datetime.now().isoformat()}}

        data = {"properties": props}
        resp = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json=data)
        if resp.status_code == 200:
            print(f"✅ Updated Notion page properties: {page_id}")
        else:
            print(f"❌ Failed to update Notion page: {resp.text}")

    # Upload report content if provided
    if report_file and os.path.exists(report_file):
        with open(report_file, "r") as f:
            content = f.read()
        
        # Helper to split text into chunks of 2000 chars
        def chunk_text(text, limit=2000):
            return [text[i:i+limit] for i in range(0, len(text), limit)]
        
        children = []
        for chunk in chunk_text(content):
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": chunk}}]
                }
            })
        
        # Batch append (Notion limit is 100 blocks, we likely have fewer)
        # If > 100 blocks, need another loop. For now, assume report is < 200k chars.
        if children:
             resp = requests.patch(f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers, json={"children": children})
             if resp.status_code == 200:
                 print(f"✅ Appended report content to Notion page ({len(children)} blocks).")
             else:
                 print(f"❌ Failed to append content: {resp.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="Path to topic folder")
    parser.add_argument("--status", help="Status to set (To Do, In Progress, Done)")
    parser.add_argument("--report", help="Path to report markdown file")
    args = parser.parse_args()
    
    sync_notion(args.path, args.status, args.report)
