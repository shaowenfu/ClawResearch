import os
import sys
import argparse
from datetime import datetime
from utils import load_config, save_state, log, get_today_str

def init_topic(topic_name):
    log(f"Initializing topic: {topic_name}")
    config = load_config()
    root_path = config["root_path"]
    topics_root = os.path.join(root_path, "Topics")
    os.makedirs(topics_root, exist_ok=True)

    # Sanitize topic name
    safe_name = "".join([c if c.isalnum() else "_" for c in topic_name])
    folder_name = f"{get_today_str()}_{safe_name}"
    full_path = os.path.join(topics_root, folder_name)
    
    # Create directories
    subdirs = ["00_Brief", "01_RawMaterials", "02_Distilled", "03_Synthesis"]
    for d in subdirs:
        os.makedirs(os.path.join(full_path, d), exist_ok=True)
    
    # Create empty report
    with open(os.path.join(full_path, "report.md"), "w") as f:
        f.write(f"# Research Report: {topic_name}\n\n## Status\nInitialized\n")

    log(f"Initialized workspace: {full_path}")
    
    # Update state
    save_state({
        "status": "running",  # Auto-start as requested
        "current_topic_path": full_path,
        "current_topic_name": topic_name,
        "last_updated": datetime.now().timestamp(),
        "total_cost_usd": 0.0,
        "total_tokens": 0
    })

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="Name of the research topic")
    args = parser.parse_args()
    init_topic(args.topic)
