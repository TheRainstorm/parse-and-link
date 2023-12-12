import argparse
import os
import json

def get_files(path):
    file_paths = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_paths.append(os.path.join(os.path.relpath(root, start=path), file))
    
    file_paths.sort()
    # pretty print file_paths
    return json.dumps(file_paths, indent=4, sort_keys=True, ensure_ascii=False)

def make_files(dst_path, file_paths):
    for file_path in file_paths:
        file_path = os.path.join(dst_path, file_path)
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        os.close(os.open(file_path, os.O_CREAT))

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s',
                        '--src',
                        help='Traverse source directory and save all file path to json file')
    parser.add_argument('-d',
                        '--dst',
                        help='Create zero-size files from json file to destination directory')
    parser.add_argument('-j',
                        '--jsonfile',
                        default="example.py.json",
                        help='specific json file name')
    args = parser.parse_args()
    
    if args.src:
        file_paths = get_files(args.src)
        with open(args.jsonfile, 'w', encoding='utf-8') as f:
            f.write(file_paths)
    if args.dst:
        with open(args.jsonfile, 'r', encoding='utf-8') as f:
            # read as python object
            file_paths = eval(f.read())
        make_files(args.dst, file_paths)
        # print(file_paths)