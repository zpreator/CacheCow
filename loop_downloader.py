import time
import subprocess

while True:
    print("⏳ Running downloader script...")
    subprocess.run(["python", "downloader.py"])
    print("✅ Finished. Sleeping 15 minutes.")
    time.sleep(15 * 60)

