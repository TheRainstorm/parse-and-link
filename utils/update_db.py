import argparse
import json
import os

parser = argparse.ArgumentParser(
    description='db add media src script'
)

parser.add_argument('-c', '--config',
                    required=True,
                    help='config file contain all media src')
parser.add_argument('--prefix',
                    required=True,
                    help='')
parser.add_argument('--prefix_sub',
                    required=True,
                    help='')
args = parser.parse_args()

def read_database(self):
    self.db_all = {}
    if os.path.exists(self.db_path):
        with open(self.db_path, 'r', encoding='utf-8') as f:
            self.db_all = json.load(f)
    self.db = self.db_all[self.ARGS.media_src]

def save_database(self):
    self.db_all[self.ARGS.media_src] = self.db
    os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    with open(self.db_path, 'w', encoding='utf-8') as f:
        json.dump(self.db_all, f, ensure_ascii=False, indent=2, default=str)

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

# options_dict = read_config()
# print(options_dict)

# for watched_dir,options in options_dict:
#     self.db_path = os.path.join(args.link_dst, 'db', f'{os.path.basename(args.media_src)}.json')

# this script is no more need now, keep for future use