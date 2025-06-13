import time
import subprocess
import os

from utils import RUN_NOW_FILE, load_config

config = load_config()

minutes_between_runs = int(config['settings'].get("minutes_between_runs", 60))
SECONDS_TO_CHECK = 5
SECONDS_BETWEEN_RUNS = 60 * minutes_between_runs

def run_downloader():
    print("⏳ Running downloader script...")
    subprocess.run(["python", "downloader.py"])
    print(f"✅ Finished. Sleeping {minutes_between_runs} minutes.")

count = 0
max_count = SECONDS_BETWEEN_RUNS / SECONDS_TO_CHECK
while True:
    # Check if the trigger file exists (manual run)
    if os.path.exists(RUN_NOW_FILE):
        os.remove(RUN_NOW_FILE)  # Clean up trigger file
        run_downloader()
        count = 0  # Reset count after manual run
        time.sleep(SECONDS_TO_CHECK)  # Small sleep to prevent immediate loop re-entry
        continue  # Go back to the start of the loop
    
    # If the max count is reached, run the downloader
    if count >= max_count:
        run_downloader()
        count = 0  # Reset count after scheduled run
    
    # Increment count and wait
    time.sleep(SECONDS_TO_CHECK)
    count += 1
