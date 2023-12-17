import os
import argparse
import json

from pal.pal import PaL

parser = argparse.ArgumentParser()
parser.add_argument('-f',
                    '--config-file',
                    default='config/example.json',
                    required=True,
                    help='The config file path')

args = parser.parse_args()
with open(args.config_file, 'r') as f:
    config = json.load(f)

pal = PaL()

default = {}
if 'default' in config:
    default = config['default']

for d in config['list']:
    print(d['media_src'])
    options = default.copy()
    options.update(d)
    pal.pal(options=options)