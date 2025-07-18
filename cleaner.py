import os
import datetime
import subprocess

from utils import load_config

def delete_old_files(directory, days):
    # Get the current time
    current_time = datetime.datetime.now()

    # Calculate the timedelta for 3 months
    timedelta = datetime.timedelta(days=days)

    # print(f"Num files: {len(os.listdir(directory))}")
    for root, dirs, files in os.walk(directory):
        for file in files:
            print(file)
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in [".mp4", ".part"]:
                file_path = os.path.join(root, file)
                print(f"Found file: {file_path}")
                # Get the last modification time of the file
                last_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                # Calculate the age of the file
                age = current_time - last_modified_time
                # Delete the file if it's older than the specified months
                print(f"Age: {age}")
                if age > timedelta:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")

def verify_file(file_path):
    try:
        # Run ffprobe to check file integrity
        subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', file_path])
        return True  # File is valid
    except subprocess.CalledProcessError:
        return False  # File is likely corrupted
    
if __name__ == "__main__":
    config = load_config()

    # Specify the directory to clean and the number of months
    if config["settings"].get("remove_old_files"):
        directory_to_clean = config["settings"].get("download_path", None)
        days_threshold = config["settings"].get("clean_threshold", None)

        if directory_to_clean and days_threshold:

            # Call the function to delete old files
            delete_old_files(directory_to_clean, days_threshold)
        else:
            raise Exception("Missing either config.settings.download_path or config.settings.clean_threshold")