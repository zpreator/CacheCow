import datetime
import os


def delete_old_files(directory, days):
    current_time = datetime.datetime.now()
    threshold = datetime.timedelta(days=days)

    for root, dirs, files in os.walk(directory):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in [".mp4", ".part"]:
                file_path = os.path.join(root, file)
                last_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                age = current_time - last_modified_time
                if age > threshold:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
