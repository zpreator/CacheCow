import time
import subprocess

while True:
    print("⏳ Running cleaner script...")
    subprocess.run(["python", "cleaner.py"])
    print("✅ Finished Cleaner script. Sleeping for 1 day.")
    time.sleep(24 * 60 * 60)

