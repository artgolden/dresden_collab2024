import os
import re
import time
import shutil
import argparse
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Timer

class NotImagePlaneFile(Exception):
    pass


class ImageFile:
    """
    File naming for light-sheet image files.
    Example file name: SPC-0001_TP-0001_ILL-0_CAM-0_CH-01_PL-0001-outOf-0150_blaBla.tif or .bmp
    :param file_path: full path to image
    :type file_path: str
    """

    timelapse_id = ""
    time_point = 0
    specimen = 0
    illumination = 0
    camera = 0
    channel = 0
    plane = 0
    total_num_planes = 0
    additional_info = ""
    extension = ""
    path_to_image_dir = ""

    def __init__(self, file_path):
        self.path_to_image_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        split_by = r"timelapseID-|SPC-|TP-|ILL-|CAM-|CH-|PL-|outOf-|\."
        name_parts = re.split(split_by, file_name)

        if len(name_parts) == 10:
            try:
                for i, name_part in enumerate(name_parts):

                    if i == 0:
                        self.dataset_name = name_part.strip("-_")
                    elif i == 1:
                        self.timelapse_id = name_part.strip("-_")
                    elif i == 2:
                        self.specimen = int(name_part.strip("-_"))
                    elif i == 3:
                        self.time_point = int(name_part.strip("-_"))
                    elif i == 4:
                        self.illumination = int(name_part.strip("-_"))
                    elif i == 5:
                        self.camera = int(name_part.strip("-_"))
                    elif i == 6:
                        self.channel = int(name_part.strip("-_"))
                    elif i == 7:
                        self.plane = int(name_part.strip("-_"))
                    elif i == 8:
                        name_and_info = name_part.strip("-_").split("_", 1)
                        if len(name_and_info) == 1:
                            self.total_num_planes = int(name_and_info[0].strip("-_"))
                        else:
                            num_planes, info = name_and_info
                            self.total_num_planes = int(num_planes.strip("-_"))
                            self.additional_info = info
                    elif i == 9:
                        self.extension = name_part
            except ValueError:
                raise NotImagePlaneFile(
                    "This is not a valid filename for a single plane image file!"
                )
        else:
            raise NotImagePlaneFile(
                "Image file name is improperly formatted! Check documentation inside the script. "
                "Expected 10 parts after splitting by %s" % split_by
            )

        self.extension.lower()

    @classmethod
    def get_ImageFile_from_xOpenSPIM_filename(cls, file_name, file_dir=""):
        instance = cls.__new__(cls)
        instance.path_to_image_dir = file_dir
        try:
            pattern = r"_channel(\d+)_position(\d+)_time(\d+)_view(\d+)_z(\d+)\.(\w+)"
            match = re.match(pattern, file_name)
            if match:
                instance.channel = int(match.group(1))
                instance.specimen = int(match.group(2))
                instance.time_point = int(match.group(3))
                instance.camera = 0
                instance.plane = int(match.group(5))
                instance.extension = match.group(6)
                instance.timelapse_id = "20240808-111112"  
                instance.illumination = 0  
                instance.total_num_planes = 1  
                instance.additional_info = ""  
                instance.dataset_name = "" 
            else:
                raise NotImagePlaneFile("xOpenSPIM file name is improperly formatted!")
        except ValueError:
            raise NotImagePlaneFile("This is not a valid custom filename for a single plane image file!")
        return instance        

    def get_name(self):
        additional_info = self.additional_info
        dataset_name = self.dataset_name
        if additional_info != "":
            additional_info = "_" + additional_info
        if dataset_name != "":
            dataset_name = dataset_name + "_"
        return (
            f"{dataset_name}timelapseID-{self.timelapse_id:}_SPC-{self.specimen:04}"
            f"_TP-{self.time_point:04}_ILL-{self.illumination}"
            f"_CAM-{self.camera}_CH-{self.channel:02}"
            f"_PL-{self.plane:04}-outOf-{self.total_num_planes:04}{additional_info}.{self.extension}"
        )

    def get_name_without_extension(self):
        return os.path.splitext(self.get_name())[0]

    def get_stack_name(self):
        additional_info = self.additional_info
        dataset_name = self.dataset_name
        if additional_info != "":
            additional_info = "_" + additional_info
        if dataset_name != "":
            dataset_name = dataset_name + "_"
        return (
            f"{dataset_name}timelapseID-{self.timelapse_id:}_SPC-{self.specimen:04}"
            f"_TP-{self.time_point:04}_ILL-{self.illumination}"
            f"_CAM-{self.camera}_CH-{self.channel:02}"
            f"_PL-(ZS)-outOf-{self.total_num_planes:04}{additional_info}.{self.extension}"
        )

    def get_stack_path(self):
        return os.path.join(self.path_to_image_dir, self.get_stack_name())

    def get_file_path(self):
        return os.path.join(self.path_to_image_dir, self.get_name())


class FileEventHandler(FileSystemEventHandler):
    def __init__(self, output_folder):
        self.output_folder = output_folder

    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(1)  # To ensure file is fully written
        self.process(event.src_path)

    def process(self, file_path):
        try:
            image_file = ImageFile.get_ImageFile_from_xOpenSPIM_filename(
                os.path.basename(file_path)
            )
            new_name = image_file.get_name()
            new_path = os.path.join(self.output_folder, new_name)
            shutil.copy(file_path, new_path)
            print(f"Copied: {file_path} to {new_path}")
        except Exception as e:
            print(f"Error while copying: {e}")


def scan_directory(input_folder, processed_files, event_handler):
    new_files = []
    for file_name in os.listdir(input_folder):
        file_path = os.path.join(input_folder, file_name)
        if os.path.isfile(file_path) and file_path not in processed_files:
            new_files.append(file_path)

    # Sort the new files by their modification time (oldest first)
    new_files.sort(key=lambda x: os.path.getmtime(x))

    for f in new_files:
        # time.sleep(2)
        event_handler.process(f)
        processed_files.add(f)


def monitor_folder(folder_to_watch, output_folder):
    processed_files = set()
    event_handler = FileEventHandler(output_folder)
    observer = Observer()
    observer.schedule(event_handler, folder_to_watch, recursive=False)
    observer.start()

    def periodic_scan():
        scan_directory(folder_to_watch, processed_files, event_handler)
        Timer(3, periodic_scan).start()

    periodic_scan()  # Start the first scan

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="Watch a directory for new file additions and collect .tif"
        "files, rename them from xOpenSPIM format and copy to output directory.",
        argument_default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Input folder path to watch."
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output folder path to save stacks."
    )
    args = parser.parse_args(sys.argv[1:])
    monitor_folder(args.input, args.output)


if __name__ == "__main__":
    main()
