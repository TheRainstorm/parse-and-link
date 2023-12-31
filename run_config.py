import os
import argparse
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

from pal.jellyfin import Jellyfin
from pal.pal import PaL

class MyHandler(FileSystemEventHandler):
    def __init__(self, options, jellyfin=None) -> None:
        super().__init__()
        self.options = options
        self.pal = PaL()
        self.jellyfin = jellyfin
    
    def run_pal(self, file_path):
        ext = os.path.splitext(file_path)[1]
        if ext in ['.mp4', '.mkv', '.avi', '.rmvb'] or ext=='.run': # trigger
            self.pal.pal(options=self.options)
            if self.jellyfin:
                code = self.jellyfin.refresh()
                logging.info(f'refresh jellyfin: {code}')
        
    def on_created(self, event):
        logging.debug(f"File created: {event.src_path}")
        self.run_pal(event.src_path)
        
    def on_deleted(self, event):
        logging.debug(f"File deleted: {event.src_path}")
        self.run_pal(event.src_path)

parser = argparse.ArgumentParser()
parser.add_argument('-c',
                    '--config-file',
                    default='config/example.json',
                    required=True,
                    help='The config file path')
parser.add_argument('-m',
                    '--monitor',
                    action='store_true',
                    help='Monitor mode, run if file created or deleted')
parser.add_argument('-j',
                    '--jellyfin-url',
                    help='Jellyfin url, ex. https://host:8096')
parser.add_argument('-k',
                    '--jellyfin-api-key',
                    help='Jellyfin API Key, add from Web: Console -> API Key')
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

jellyfin = None
if args.jellyfin_url and args.jellyfin_api_key:
    jellyfin = Jellyfin(args.jellyfin_url, args.jellyfin_api_key)

def read_config():
    # read config file
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    default = {}
    if 'default' in config:
        default = config['default']

    options_dict = {}
    for d in config['list']:
        options = default.copy()
        options.update(d)
        options_dict[d['media_src']] = options
    return options_dict

options_dict = read_config()

if args.monitor:
    observers = []
    for watched_dir,options in options_dict.items():
        # add observer
        logging.info(f'watched_dir: {watched_dir}')
        event_handler = MyHandler(options, jellyfin=jellyfin)
        observer = Observer()
        observer.schedule(event_handler, path=watched_dir, recursive=True)
        observers.append(observer)

    for observer in observers:
        observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info('KeyboardInterrupt')
        for observer in observers:
            observer.stop()

    for observer in observers:
        observer.join()
else:
    for watched_dir,options in options_dict.items():
        pal = PaL()
        pal.pal(options=options)
    if jellyfin:
        code = jellyfin.refresh()
        logging.info(f'refresh jellyfin: {code}')