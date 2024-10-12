import os
import datetime

print("Hello world")
def delete_old_files(directory, months):
    # Get the current time
    current_time = datetime.datetime.now()

    # Calculate the timedelta for 3 months
    timedelta = datetime.timedelta(days=months*30)

    # print(f"Num files: {len(os.listdir(directory))}")
    cleaned = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            print(file)
            if os.path.splitext(file)[1] == ".txt":
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
                cleaned.append(file_path)
    with open("/home/glados/pythonscripts/youtubedl_clean.txt", "w") as file:
        file.write(f"Ran on: {datetime.datetime.now().isoformat()}\n")
        for file_path in cleaned:
            file.write(f"Removed: {file_path}\n")

# Specify the directory to clean and the number of months
directory_to_clean = '/home/glados/SharedMedia/Media/YouTube'
months_threshold = 3

# Call the function to delete old files
delete_old_files(directory_to_clean, months_threshold)
