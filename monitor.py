import os
import argparse
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

from db_utils import *

class MyHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        
    def on_created(self, event):
        print(f"File created: {event.src_path}")
        
    def on_deleted(self, event):
        # print(f"[Monitor] deleted file: {event.src_path}")
        if event.is_directory:
            print(f"[Monitor] deleted directory: {event.src_path}")
            delete_link_src(args.db_dir, args.link_dst, event.src_path)
        else:
            pass
            # filename, ext = os.path.splitext(event.src_path)
            # if ext in ['.mp4', '.mkv', '.avi', '.rmvb']:
            #     delete_link_src(args.db_dir, event.src_path, is_dir=event.is_directory)

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--db-dir',
                    required=True,
                    help='db dir')
parser.add_argument('-l', '--link_dst',
                    required=True,
                    help='The link dst, will monitor this dir')
parser.add_argument('-v',
                    '--verbose',
                    action='store_true',
                    help='Verbose mode, print debug')
args = parser.parse_args()

observer = Observer()
observer.schedule(MyHandler(), path=args.link_dst, recursive=True)

try:
    observer.start()
    observer.join()
except KeyboardInterrupt:
    print('KeyboardInterrupt')
    observer.stop()
    observer.join()
