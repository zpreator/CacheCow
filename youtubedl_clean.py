import os
import datetime
import subprocess

def delete_old_files(directory, months):
    # Get the current time
    current_time = datetime.datetime.now()

    # Calculate the timedelta for 3 months
    timedelta = datetime.timedelta(days=months*30)

    # print(f"Num files: {len(os.listdir(directory))}")
    for root, dirs, files in os.walk(directory):
        for file in files:
            print(file)
            file_ext = os.path.splitext(file)[1]
            if file_ext == ".txt" or file_ext == 'jpg':
                continue
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
                # cleaned.append(file_path)
    # with open("/home/glados/pythonscripts/youtubedl_clean.txt", "w") as file:
    #     file.write(f"Ran on: {datetime.datetime.now().isoformat()}\n")
    #     for file_path in cleaned:
    #         file.write(f"Removed: {file_path}\n")

def verify_file(file_path):
    try:
        # Run ffprobe to check file integrity
        subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', file_path])
        return True  # File is valid
    except subprocess.CalledProcessError:
        return False  # File is likely corrupted
    
# Specify the directory to clean and the number of months
directory_to_clean = '/home/glados/SharedMedia/Media/YouTube'
months_threshold = 3

# Call the function to delete old files
delete_old_files(directory_to_clean, months_threshold)

# Specify text files to delete
logs_to_delete = [
    "/home/glados/youtubedl-docker/youtubedl2.txt",
    "/home/glados/youtubedl-docker/letterboxd_to_radarr.txt"
]

# Delete logs
for log in logs_to_delete:
    os.remove(log)
print("Deleted Logs")

# # Delete any corrupted youtube files
# for root, dirs, files in os.walk(directory_to_clean):
#     for file in files:
#         if not verify_file(file):
#             # os.remove(file)
#             print(f"Corrupted file: {file}")