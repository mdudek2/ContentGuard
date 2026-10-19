import os
import shutil

def clear_directory(directory):
    for item in os.listdir(directory):
        path = os.path.join(directory, item)

        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)

target_directory = r"thumbnails"

clear_directory(target_directory)

print("Directory contents deleted successfully.")