import os
import argparse
import logging
import re
import json
from types import SimpleNamespace

if __name__ == "__main__":
    from ignore_matcher import IgnoreMatcher
    from walklevel import walklevel
else:
    from pal.ignore_matcher import IgnoreMatcher
    from pal.walklevel import walklevel

class PaL:
    def __init__(self):
        self.ARGS = None
        self.video_exts = ['.mkv', '.mp4', '.avi']
        self.running_db = {}
    
    def get_argparser(self):
        parser = argparse.ArgumentParser(
            description='PAL: parse metadata from filename, and link to dest path'
        )
        parser.add_argument('-s', '--media-src',
                            required=True,
                            help='The src path contains TVs or Movies')
        parser.add_argument('-d', '--link-dst',
                            required=True,
                            help='the dest path link to')
        parser.add_argument('-U', '--update-mode',
                            action='store_true',
                            help='Only check db diff, don\'t scan media src')
        parser.add_argument('-H', '--hard-link',
                            action='store_true',
                            help='use hard link rather than symbol link')
        parser.add_argument('-S', '--symbol-link',
                            action='store_true',
                            help='use symbol link rather than hard link')
        parser.add_argument('-t', '--type',
                            type=int,
                            default=0,
                            help='Specify the src media type, 0: tv, 1: movie, default TV')
        parser.add_argument('--tv-folder',
                            default="TV",
                            help='Specify the linking category-dir of TV, default `TV`')
        parser.add_argument('--movie-folder',
                            default="Movie",
                            help='Specify the linking category-dir of Movie, default `Movie`')
        parser.add_argument('--db-path',
                            help='Specify the database path')
        parser.add_argument('--upgrade',
                            default=0,
                            help='Upgrade database format')
        parser.add_argument('--filter-size',
                            default=100, # MB
                            help='Filter video smaller than this size, default 100MB')
        parser.add_argument('--filter-shortname',
                            default=0,
                            help='Filter video filename shorter than this lenght, default 0(no filter)')
        parser.add_argument('--keep-sub',
                            action='store_true',
                            help='Keep subtitles files(\'srt,ass\')')
        parser.add_argument('-F', '--force-relink-check',
                            action='store_true',
                            help='Check wheather link exists, relink if lost. Useful when changing link dst')
        parser.add_argument('--dryrun',
                            action='store_true',
                            help="Don't make really links")
        parser.add_argument('-l', '--log',
                            default="",
                            help='log file path')
        parser.add_argument('--loglevel',
                            default='INFO',
                            help='--log=DEBUG, INFO, WARNING, ERROR, CRITICAL')
        parser.add_argument('--failed-json',
                            default='failed.json',
                            help='Dump parsed failed files to json file, default `failed.json`')
        # parser.add_argument('--imdbid',
        #                     default='',
        #                     help='specify the IMDb id')
        # parser.add_argument('--tmdbid',
        #                     default='',
        #                     help='specify the TMDb id')
        return parser
        
    def process_args(self, args):
        args.media_src = os.path.expanduser(args.media_src)
        args.link_dst = os.path.expanduser(args.link_dst)
        os.makedirs(args.link_dst, exist_ok=True)

        args.filter_size = int(args.filter_size)
        args.filter_shortname = int(args.filter_shortname)
        # logging
        numeric_level = getattr(logging, args.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % args.loglevel)
        if args.log!="":
            logging.basicConfig(filename=args.log, level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        else:
            logging.basicConfig(level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        if args.db_path:
            self.db_path = args.db_path
        else:
            self.db_path = os.path.join(args.link_dst, 'db', f'{os.path.basename(args.media_src)}.json')
        
        # check type
        args.type = 'episode' if args.type == 0 else 'movie'
        self.ARGS = args
        return args

    def load_args_dicts(self, options, parser):
        args = "-s a -d b -t 0"
        default_option = parser.parse_args(args.split())
        options_new = default_option.__dict__.copy()
        options_new.update(options)
        return SimpleNamespace(**options_new)
    
    def is_videofile(self, filename):
        ext = os.path.splitext(filename)[1]
        if ext in self.video_exts:
            return True
        return False
    
    def get_interest_files(self, scan=True, input_files=None):
        if scan:
            file_paths, deleted_files = self.scan_directory(self.ARGS.media_src)
        else:
            if input_files:
                file_paths = self.abspath2rel_src(input_files)
            else:
                file_paths = self.get_db_diff_files()
            file_paths, deleted_files = self.filter_deleted_files(file_paths)
        
        self.process_deleted(deleted_files)
        return file_paths
    
    def get_db_diff_files(self):
        # get meta modified file: db - running_db
        diff_files = []
        for file_path in self.db:
            if file_path not in self.running_db:
                diff_files.append(file_path)
                continue
            if self.db[file_path]!=self.running_db[file_path]:
                diff_files.append(file_path)
        for file_path in self.running_db:
            if file_path not in self.db:
                diff_files.append(file_path)
        
        return diff_files
        
    def scan_directory(self, path):
        file_paths = []
        for root, dirs, files in walklevel(path, 2):
            for file in files:
                if not self.is_videofile(file):
                    continue
                # filter small video
                if os.path.getsize(os.path.join(root, file)) < self.ARGS.filter_size*1024*1024:
                    continue
                
                # filter short name video
                if len(file)<=self.ARGS.filter_shortname:
                    continue
                file_path = os.path.join(root, file)
                file_paths.append(os.path.relpath(file_path, self.ARGS.media_src))
        
        deleted_files = []
        for file_path in self.db:
            if file_path not in file_paths: # database have excess file
                deleted_files.append(file_path)
        
        return file_paths, deleted_files
    
    def filter_deleted_files(self, file_paths):
        # deleted file: not in src dir, but in db
        existed_files = []
        deleted_files = []
        for file_path in file_paths:
            # check delete
            if os.path.exists(os.path.join(self.ARGS.media_src, file_path)):
                existed_files.append(file_path)
                continue
            if file_path in self.db:
                deleted_files.append(file_path)
        return existed_files, deleted_files
    
    def process_deleted(self, deleted_files):
        # normal: delete target link + delete db
        # TODO: for transcode file
        # link/move back to src dir(with structed name and dir), keep link dir not change
        # db: delete old item, update to new src
        for file_path in deleted_files:
            meta = self.db[file_path]
            if 'link_relpath' in meta:
                # delete link
                self.remove_link(meta['link_relpath'], meta['type'])
            del self.db[file_path]

    def ignore_files(self, file_paths): 
        # create default ignore file
        ignorefile_path = os.path.join(self.ARGS.media_src, 'skip.txt')
        if not os.path.exists(ignorefile_path):
            with open(ignorefile_path, 'w', encoding='utf-8') as f:
                f.write('/Sample\n')
                f.write('/SP\n')     # SPs, SP DISK
                f.write('/Special\n')     # SPs, SP DISK
                f.write('Extras/\n')
        ignorer = IgnoreMatcher(ignorefile_path)
        
        # filter files
        filter_files = []
        for file_path in file_paths:
            if file_path in self.db:
                # delete files setted ignored manually
                if 'ignore' in self.db[file_path]:
                    # if already linked, remove
                    if 'link_relpath' in self.db[file_path]:
                        self.remove_link(self.db[file_path]['link_relpath'], self.db[file_path]['type'])
                        del self.db[file_path]['link_relpath']
                    continue
            if ignorer.is_ignored(file_path):
                logging.debug(f"Ignore: {file_path}")
                if file_path in self.db: 
                    logging.info(f"db found ignored: {file_path}")
                    # if already linked, remove
                    if 'link_relpath' in self.db[file_path]:
                        self.remove_link(self.db[file_path]['link_relpath'], self.db[file_path]['type'])
                    del self.db[file_path]
                continue
            filter_files.append(file_path)
        
        return filter_files

    def link(self, src, dst):
        if self.ARGS.dryrun:
            return
        if self.ARGS.symbol_link or not self.ARGS.hard_link:
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst)
        else:
            os.link(src, dst)
    
    def remove_link(self, link_relpath, type):
        def check_empty(dirpath):
            # check dir don't contain video file
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
        
        link_path = os.path.join(self.ARGS.link_dst, link_relpath)
        
        if os.path.exists(link_path) or \
           os.path.islink(link_path): # broken link: not exist but is link
            logging.info(f"Remove: {os.path.relpath(link_path, self.ARGS.link_dst)}")
            os.remove(link_path)
        else:
            return
        
        dirpath = os.path.join(link_path, "..")
        dirpath = os.path.abspath(dirpath)
        
        # delete movie dir or season dir
        if check_empty(dirpath):
            logging.info(f"Remove dir: {os.path.relpath(dirpath, self.ARGS.link_dst)}")
            delete_dir(dirpath)
        if type == 'episode':
            dirpath = os.path.join(link_path, "../../")
            dirpath = os.path.abspath(dirpath)
            if check_empty(dirpath):
                logging.info(f"Remove dir: {os.path.relpath(dirpath, self.ARGS.link_dst)}")
                delete_dir(dirpath)

    def read_database(self):
        self.db_all = {}
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                print(f"{self.db_path=}")
                self.db_all = json.load(f)
        self.db = self.db_all.get(self.ARGS.media_src, {})
    
    def save_database(self):
        self.db_all[self.ARGS.media_src] = self.db
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.db_all, f, ensure_ascii=False, indent=2, default=str)
    
    def clear_failed_files(self):
        self.failed_files = {}
        self.failed_files['title'] = {}
        self.failed_files['ep'] = {}
        self.failed_files['type'] = {}
        if os.path.exists(self.ARGS.failed_json):
            with open(self.ARGS.failed_json, 'r', encoding='utf-8') as f:
                self.failed_files = json.load(f)
        
    def parse_meta(self, file_path):
        from guessit import guessit
        
        # output = self.run_cmd(f'guessit "{filename}"')
        # m = re.search(r'{.*}', output, re.M |re.DOTALL)
        # if not m:
        #     return None
        # meta = json.loads(m.group(0))
        # return meta
        filename = os.path.basename(file_path)
        meta = guessit(filename)
        return dict(meta)
    
    # def parse_filename_gpt(self, filename):
    #     from Spark.Spark_parser import get_metadata
    #     meta = get_metadata([filename])
    
    def upgrade1_add_meta(self, file_path, meta):
        # add more meta
        filename = os.path.basename(file_path)
        ext_name = os.path.splitext(filename)[1]
        m = re.search(r'\d{3,4}', meta['screen_size'])
        resolution_str = f".{m.group()}p" if m else ''
        if resolution_str not in ['.720p', '.1080p', '.2160p']:
            resolution_str = ''
        meta['ext'] = ext_name
        meta['resolution_str'] = resolution_str
        return meta
        
    def check_fix_meta(self, file_path, meta):
        # return value
        '''code, msg
        0: ok
        1: no season
        2: miss title
        3: miss type
        4: miss episode
        5: bad season
        9: link exist
        '''
        code, msg = 0, "ok"
        
        # little fix
        if 'screen_size' not in meta:
            meta['screen_size'] = ''
        if 'year' not in meta:
            meta['year'] = ''

        filename = os.path.basename(file_path)
        # try fix: title -> type -> episode -> season
        def try_fix():
            nonlocal code, msg
            # title
            def fix_title():
                m = re.match(r'^(\[[^\]]+\])+(\(.*\))?\..*$', filename)
                if m: # [xxx][title][xxx].mkv
                    parts = re.split(r'\[|\]', filename)
                    filename_ = max(parts, key=len) # get longest part
                    filename_ = filename_.strip().replace('_', ' ')
                    meta['title'] = filename_
                    return True
                return False
            
            if 'title' not in meta:
                fixed = fix_title()
                if not fixed:
                    self.failed_files['title'][file_path] = meta
                    code, msg = 2, "miss title"
                    return
            if ':' in meta['title']: # fix: SMB windows display bug
                meta['title'] = meta['title'].replace(':', ' ')
            
            # type not consistent
            if meta['type'] != self.ARGS.type:
                # have ep and no year
                if re.search(r'\b\d{1,2}\b', filename) and \
                    not re.search(r'(?![x])\d{4}(?![pPx])', filename):  # 1080p, 1920x1080
                    meta['type'] = 'episode'
                else:
                    self.failed_files['type'][file_path] = meta
                    code, msg = 3, "miss type"
                    return
            
            # episode
            def fix_episode():
                # [01]
                m = re.search(r'\[(\d{2})\]', filename)
                if m:
                    ep = int(m.group(1))
                    filename_ = filename.replace(m.group(0), '')
                    # reparse, may fix season
                    meta_new = self.parse_meta(filename_)
                    meta['episode'] = ep
                    if 'season' in meta_new:
                        meta['season'] = meta_new['season']
                    return
                # - 9
                m = re.search(r'\b(\d{1,2})\b', filename)
                if m:
                    meta['episode'] = int(m.group(1))
                    return
                meta['episode'] = []
            
            def fix_season():
                # can't fix
                if 'season' in meta and type(meta['season'])==list:
                    code, msg = 5, "bad season"
                    return True
                # season in title
                m = re.search(r'(2nd Season)|(II)', meta['title'], re.I)
                if m:
                    meta['season'] = 2
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    return True
                m = re.search(r'(3rd Season)|(III)', meta['title'], re.I)
                if m:
                    meta['season'] = 3
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    return True
                # title - 2$
                if re.search(r'[\s_-]\d{1}$', meta['title']):
                    meta['season'] = int(meta['title'][-1])
                    meta['title'] = meta['title'][:-1].strip()
                    return True
                return False
            
            if meta['type'] == 'episode':
                if 'episode' not in meta or \
                    type(meta['episode'])==list:
                    fix_episode()
                if type(meta['episode'])==list:
                    self.failed_files['ep'][file_path] = meta
                    code, msg = 4, "miss episode"
                    return
                if 'season' not in meta:
                    if not fix_season():
                        # simple fix
                        meta['season'] = 1
                        code = 1 # still ok
                        return
                    if meta['season'] > 20:
                        code, msg = 5, "bad season"
                        return
        try_fix()
        meta['code'] = code
        meta['msg'] = msg
        if msg != "ok":
            meta['failed'] = 1 # add failed flag
        else:
            if 'failed' in meta:
                del meta['failed'] # remove failed flag
        
        return meta, code, msg

    def make_link(self, file_path, meta):
        # make up link path
        version_tags = []
        if '1080' not in meta['screen_size']:
            version_tags.append(meta['screen_size'])  # 2160p, 720p
        version_str_ = '|'.join(version_tags)  # connect multiple tags
        version_str = f" - {version_str_}" if version_str_ else '' # check empty
        if meta['type'] == 'episode':
            # /link/TV/Title/Season 1/Title-S01E01 - 2160p.mkv
            link_relpath = os.path.join(self.ARGS.tv_folder, meta['title'], f"Season {meta['season']}", f"{meta['title']}-S{meta['season']:02d}E{meta['episode']:02d}{version_str}{meta['ext']}")
        else: #movie
            # /link/Movie/Title (year)/Title (year) - 2160p.mkv
            year_str = f" ({meta['year']})" if meta['year'] else ''
            
            link_relpath = os.path.join(self.ARGS.movie_folder, f"{meta['title']}{year_str}", f"{meta['title']}{year_str}{version_str}{meta['ext']}")

        # already linked
        if 'link_relpath' in meta:
            # same link path, return. if forece_relink_check, don't return
            if meta['link_relpath'] == link_relpath and not self.ARGS.force_relink_check:
                return
            if meta['link_relpath'] != link_relpath:
                # different, remove old link
                self.remove_link(meta['link_relpath'], meta['type'])
        
        link_path = os.path.join(self.ARGS.link_dst, link_relpath)
        # update meta
        meta['link_relpath'] = link_relpath
        
        # link exists, skip
        if os.path.exists(link_path):
            if not self.ARGS.force_relink_check:
                meta['code'] = 9  # link exists, duplicate source
            return
        meta['code'] = 0
        
        # ensure the link dir exists
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        logging.info(f"{file_path:50} -> {link_relpath}")
        
        # symlink or hardlink to dest path
        self.link(os.path.join(self.ARGS.media_src, file_path), link_path)

    def process_files(self, file_paths):
        diff_files = []  # meta modified
        new_files = []
        for file_path in file_paths:
            if file_path in self.db:
                logging.debug(f" Hit: {file_path}")
                if self.ARGS.upgrade>=1:
                    self.upgrade1_add_meta(file_path, self.db[file_path])
                
                if file_path not in self.running_db or \
                    self.db[file_path]!=self.running_db[file_path]:
                    diff_files.append(file_path)
            else:
                new_files.append(file_path)
        
        # record failed files
        self.clear_failed_files()
        
        for file_path in new_files:
            # meta from filename
            meta = self.parse_meta(file_path)
            # fix meta
            meta, code, msg = self.check_fix_meta(file_path, meta)
            if msg != "ok": # parse failed
                logging.warning(f" {msg:10}: {file_path}")
            # add more meta info
            meta = self.upgrade1_add_meta(file_path, meta)
            self.db[file_path] = meta

        # log failed files
        if self.ARGS.failed_json != "":
            with open(self.ARGS.failed_json, 'w', encoding='utf-8') as f:
                json.dump(self.failed_files, f, ensure_ascii=False, indent=2, default=str)
        
        return diff_files + new_files
    
    def abspath2rel_src(self, file_paths):
        cvt_file_paths = []
        for file_path in file_paths:
            cvt_file_paths.append(
                os.path.relpath(file_path, self.ARGS.media_src))
        return cvt_file_paths
    
    def pal(self, argv=None, options=None):
        parser = self.get_argparser()
        if options is None:
            args = parser.parse_args(argv)
        else:
            args = self.load_args_dicts(options, parser)
        self.process_args(args)
        
        if self.ARGS.update_mode:
            self.run(scan=False)
        else:
            self.run()
    
    def server(self):
        pass

    def run(self, scan=True, input_files=None):
        # read database(can be empty), self.db
        self.read_database()
        
        # get interested files we will process
        file_paths = self.get_interest_files(scan, input_files)
        
        # filter files according ignore rules
        file_paths = self.ignore_files(file_paths)
        
        # new files + diff files
        changed_files = self.process_files(file_paths)
        
        for file_path in changed_files:
            meta = self.db[file_path]
            # check meta again, set or clear failed flag by newest metadata
            _,_,msg = self.check_fix_meta(file_path, meta)
            if msg != "ok":
                continue
            try:
                self.make_link(file_path, meta)
            except Exception as e:
                logging.error(f"{e}")
                logging.error(f"Make link failed: {file_path} \n{json.dumps(meta, ensure_ascii=False, indent=2, default=str)}")
        
        # write database
        self.save_database()

if __name__ == '__main__':
    pal = PaL()
    pal.pal()