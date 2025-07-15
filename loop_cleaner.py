import time
import os
import subprocess

from utils import PROGRESS_FILE, STOP_FILE, RUN_NOW_FILE

# Clean up any existing trigger or progress files
for file in [PROGRESS_FILE, STOP_FILE, RUN_NOW_FILE]:
    if os.path.exists(file):
        os.remove(file)

while True:
    print("⏳ Running cleaner script...")
    subprocess.run(["python", "cleaner.py"])
    print("✅ Finished Cleaner script. Sleeping for 1 day.")
    time.sleep(24 * 60 * 60)

