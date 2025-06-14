import os
import json

CONFIG_FILE = "data/config.json"
ARCHIVE_FILE = "data/archive.txt"
PROGRESS_FILE = "data/temp/progress.json"
RUN_NOW_FILE = "data/run_now.trigger"
STOP_FILE = "data/stop.trigger"

# Function to load config file
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    empty_config = {
        "youtube": {},
        "tags": ["other"],
        "settings": {}
    }
    return empty_config

# Function to save config file
def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)