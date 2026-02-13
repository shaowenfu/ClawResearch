import json
import os
import time
from datetime import datetime

CONFIG_PATH = os.path.expanduser("~/clawd/research/config.json")
STATE_PATH = os.path.expanduser("~/clawd/research/state.json")
LOG_PATH = os.path.expanduser("~/clawd/research/research.log")

# --- Cost Constants (Estimates) ---
# Pricing per 1M tokens (Approx. based on Claude 3.5 Sonnet / GPT-4o mix)
PRICE_INPUT_1M = 3.00  
PRICE_OUTPUT_1M = 15.00

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_state(updates):
    state = load_state()
    state.update(updates)
    state['last_updated'] = time.time()
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)

def log(message, level="INFO"):
    """Write log to file and print to stdout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")

def estimate_tokens(text):
    """Rough estimate: 1 token ~= 4 chars"""
    if not text:
        return 0
    return len(text) // 4

def track_cost(operation, input_text="", output_text="", model="unknown"):
    """Log cost and update state"""
    in_tok = estimate_tokens(input_text)
    out_tok = estimate_tokens(output_text)
    
    cost = (in_tok / 1_000_000 * PRICE_INPUT_1M) + (out_tok / 1_000_000 * PRICE_OUTPUT_1M)
    
    state = load_state()
    total_cost = state.get("total_cost_usd", 0.0)
    total_tokens = state.get("total_tokens", 0)
    
    updates = {
        "total_cost_usd": total_cost + cost,
        "total_tokens": total_tokens + in_tok + out_tok
    }
    save_state(updates)
    
    log(f"COST: {operation} | In: {in_tok} | Out: {out_tok} | Est. $: {cost:.5f}", level="METRICS")

def get_today_str():
    return datetime.now().strftime("%Y%m%d")
