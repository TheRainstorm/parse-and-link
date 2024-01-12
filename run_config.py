import os
import argparse
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import threading
import queue

from pal.jellyfin import Jellyfin
from pal.pal import PaL

class MyHandler(FileSystemEventHandler):
    def __init__(self, options, event, queue) -> None:
        super().__init__()
        self.options = options
        self.event = event
        self.queue = queue
    
    def push_queue(self, file_path):
        ext = os.path.splitext(file_path)[1]
        if ext in ['.mp4', '.mkv', '.avi', '.rmvb'] or ext=='.run': # trigger
            self.queue.put(file_path)
            self.event.set()
        
    def on_created(self, event):
        logging.debug(f"File created: {event.src_path}")
        self.push_queue(event.src_path)
        
    def on_deleted(self, event):
        logging.debug(f"File deleted: {event.src_path}")
        self.push_queue(event.src_path)

exit_flag = False
def pal_worker(event, queue, options):
    while not exit_flag:
        event.wait()
        if exit_flag:
            break
        while not queue.empty():
            file = queue.get()
            logging.info(f'queue: {file}')
            time.sleep(1)
        event.clear()
        # no new queue push in 1s
        logging.info(f'run pal')
        pal = PaL()
        pal.pal(options=options)
        if jellyfin:
            code = jellyfin.refresh()
            logging.info(f'refresh jellyfin: {code}')

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
parser.add_argument('-v',
                    '--verbose',
                    action='store_true',
                    help='Verbose mode, print debug')
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, 
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# Set jellyfin API object, can refresh jellyfin library
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

# every watched_dir has a options
options_dict = read_config()

if args.monitor:
    observers = []
    pal_threads = []
    event_list = []
    for watched_dir,options in options_dict.items():
        q = queue.Queue()
        event = threading.Event()
        event_list.append(event)
        # add observer
        logging.info(f'watched_dir: {watched_dir}')
        observer = Observer()
        observer.schedule(MyHandler(options, event, q), path=watched_dir, recursive=True)
        observers.append(observer)
        observer.start()
        
        # threading
        pal_thread = threading.Thread(target=pal_worker, args=(event, q, options))
        pal_thread.start()
        pal_threads.append(pal_thread)
    try:
        for pal_thread in pal_threads:
            pal_thread.join()
    except KeyboardInterrupt:
        logging.info('KeyboardInterrupt')
        for observer in observers:
            observer.stop()
        exit_flag = True
        for event in event_list:
            event.set()
    # wait all exit
    for observer in observers:
        observer.join()
    for pal_thread in pal_threads:
        pal_thread.join()
else:
    # link all watched_dir
    for watched_dir,options in options_dict.items():
        pal = PaL()
        pal.pal(options=options)
    if jellyfin:
        code = jellyfin.refresh()
        logging.info(f'refresh jellyfin: {code}')