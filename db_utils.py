import os
import argparse
import logging
import re
import json
from types import SimpleNamespace

# helper functions
def try_delete_file_parent_dir(file_path):
    def check_empty(dirpath):
        # check dir don't contain video file, and only contain '.nfo', '.jpg', '.png'
        for file in os.listdir(dirpath):
            file_path = os.path.join(dirpath, file)
            if os.path.isdir(file_path):
                if not check_empty(file_path):
                    return False
            else:
                ext = os.path.splitext(file)[1]
                if ext not in ['.nfo', '.jpg', '.png']:
                    return False
        return True

    def delete_dir(dirpath):
        # delete dir recursively
        for file in os.listdir(dirpath):
            file_path = os.path.join(dirpath, file)
            if os.path.isdir(file_path):
                delete_dir(file_path)
            else:
                os.remove(file_path)
        os.rmdir(dirpath)
    
    dirpath = os.path.join(file_path, "..")
    dirpath = os.path.abspath(dirpath)
    if check_empty(dirpath):
        print(f"Remove dir: {dirpath}")
        delete_dir(dirpath)
    # delete TV dir
    dirpath = os.path.join(dirpath, "..")
    dirpath = os.path.abspath(dirpath)
    if check_empty(dirpath):
        print(f"Remove dir: {dirpath}")
        delete_dir(dirpath)

# db functions
def read_all_db(db_dir):
    db_all = {}
    for file in os.listdir(db_dir):
        if file.endswith('.json'):
            db_path = os.path.join(db_dir, file)
            with open(db_path, 'r', encoding='utf-8') as f:
                db_all[file] = json.load(f)
    return db_all

def read_db(db_path):
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(db_path, db):
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2, default=str)

def db_delete_file(db, media_src, src_file):
    if media_src in db:
        if 'seeding' in db[media_src]:
            if src_file in db[media_src]['seeding']:
                del db[media_src]['seeding'][src_file]
                return True
    return False

def db_check_file(db_all, media_src, src_file):
    if media_src in db_all:
        if 'seeding' in db_all[media_src]:
            if src_file in db_all[media_src]['seeding']:
                return True
    return False
 
def save_database(db_dir, db_all):
    for file in db_all:
        db_path = os.path.join(db_dir, file)
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db_all[file], f, ensure_ascii=False, indent=2, default=str)

def get_all_db_link_index(db_all, link_dst):
    # mapping link file to src file
    link_index = {}
    for db_file, db_L1 in db_all.items():  # file level
        for media_src, db_L2 in db_L1.items():  # media_src level
            for src_file, video_info in db_L2.items():  # seeding level
                try:
                    link_file_path = os.path.join(link_dst, video_info['link_relpath'])
                except:
                    print(f"warning: {src_file=} {video_info['title']=} link_relpath not found")
                    continue
                if link_file_path in link_index:
                    print(f"warning: indexing already exists: {db_file=} {media_src=} {src_file=} to {link_file_path=} ")
                link_index[link_file_path] = {
                    'src_file': src_file,
                    'media_src': media_src,
                    'db_file': db_file
                }
    return link_index

def find_prefix_matched(link_index, link_path):
    matched = {}
    for link_file_path, index_info in link_index.items():
        if link_file_path.startswith(link_path):
            matched[link_file_path] = index_info
    return matched

link_index = None
db_all = None
def delete_link_src(db_dir, link_dst, link_path):
    # delete all prefix matched src file corresponding to link_path
    # link_path can be a file or a dir
    global link_index
    global db_all
    
    if link_index is None:
        # read all json db files
        db_all = read_all_db(db_dir)
        # index link_dst to src_file
        link_index = get_all_db_link_index(db_all, link_dst)
    
    # find all prefix match
    prefix_matcheds = find_prefix_matched(link_index, link_path)
    
    # delete all
    modified_db_files = set()
    for link_file_path,index_info in prefix_matcheds.items():
        src_file_path = os.path.join(index_info['media_src'], index_info['src_file'])
        
        os.remove(src_file_path)
        print(f"delete: {link_path} --> {src_file_path}")
        
        # delete dir if empty
        try_delete_file_parent_dir(src_file_path)
        
        modified_db_files.add(index_info['db_file'])
        db = db_all[index_info['db_file']]
        # print("before", db_check_file(db, index_info['media_src'], index_info['src_file']))
        db_delete_file(db, index_info['media_src'], index_info['src_file'])
        # print("after delete", db_check_file(db, index_info['media_src'], index_info['src_file']))
        
        # update cache
        del link_index[link_file_path]
    
    if len(prefix_matcheds) == 0:
        print(f"warning: {link_path} source not found")
    else:
        # update db finally
        for db_file, db in db_all.items():
            if db_file not in modified_db_files:
                continue
            db_path = os.path.join(db_dir, db_file)
            save_db(db_path, db)
    
if __name__ == '__main__':
    import sys
    if len(sys.argv) != 4:
        print("usage: db_dir link_dst filepath(or dirname)")
        sys.exit(1)
    db_dir = sys.argv[1]
    link_dst = sys.argv[2]
    file_path = sys.argv[3]
    delete_link_src(db_dir, link_dst, file_path)
    