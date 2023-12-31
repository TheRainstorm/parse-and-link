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
        self.parser = None
        self.ARGS = None
        self.video_exts = ['.mkv', '.mp4', '.avi']
        self.min_video_size = 100*1024*1024 # 100MB
        self.skip_dirnames = []
    
    def set_argparser(self):
        parser = argparse.ArgumentParser(
            description='PAL: parse metadata from filename, and link to dest path'
        )
        parser.add_argument('-s',
                            '--media-src',
                            required=True,
                            help='The src path contains TVs or Movies')
        parser.add_argument('-d',
                            '--link-dst',
                            required=True,
                            help='the dest path link to')
        # parser.add_argument('--tmdb-api-key',
        #                     # required=True,
        #                     help='Search API for the tmdb id, and gen dirname as Name (year)\{tmdbid=xxx\}')
        parser.add_argument('-S',
                            '--symbol-link',
                            action='store_true',
                            help='use symbolic link rather than hard link')
        # parser.add_argument('--only-link',
        #                     action='store_true',
        #                     help='don\'t save .nfo file in the media dir')
        parser.add_argument('-t',
                            '--type',
                            type=int,
                            required=True,
                            help='Specify the src media type, 0: tv, 1: movie, default TV')
        parser.add_argument('--tv-folder',
                            default="TV",
                            help='Specify the linking category-dir of TV, default `TV`')
        parser.add_argument('--movie-folder',
                            default="Movie",
                            help='Specify the linking category-dir of Movie, default `Movie`')
        parser.add_argument('--ignore-rule',
                            default="skip.txt",
                            help='Specific ignored files and directories. One rule per line. `!` cancel ignoring')
        parser.add_argument('--keep-sub',
                            action='store_true',
                            help='Keep subtitles files(\'srt,ass\')')
        parser.add_argument('-F',
                            '--force-relink-check',
                            action='store_true',
                            help='Check wheather link exists, relink if lost. Useful when changing link dst')
        parser.add_argument('--dryrun',
                            action='store_true',
                            help="Don't make really links")
        parser.add_argument('--make-log',
                            action='store_true',
                            help='Print log to file "pal.log"')
        parser.add_argument('--loglevel',
                            default='INFO',
                            help='--log=DEBUG, INFO, WARNING, ERROR, CRITICAL')
        parser.add_argument('--failed-json',
                            default='failed.json',
                            help='Dump failed files to json file, default `failed.json`')
        # parser.add_argument('--imdbid',
        #                     default='',
        #                     help='specify the IMDb id')
        # parser.add_argument('--tmdbid',
        #                     default='',
        #                     help='specify the TMDb id')
        self.parser = parser
        
    def process_args(self, args):
        args.media_src = os.path.expanduser(args.media_src)
        args.link_dst = os.path.expanduser(args.link_dst)
        os.makedirs(args.link_dst, exist_ok=True)

        # logging
        numeric_level = getattr(logging, args.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % args.loglevel)
        if args.make_log:
            logging.basicConfig(filename='pal.log', level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        else:
            logging.basicConfig(level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        
        # check type
        args.type = 'episode' if args.type == 0 else 'movie'
        self.ARGS = args
        return args

    def load_args_dicts(self, options):
        args = "-s a -d b -t 0"
        default_option = self.parser.parse_args(args.split())
        options_new = default_option.__dict__.copy()
        options_new.update(options)
        return SimpleNamespace(**options_new)
    
    def is_videofile(self, filename):
        ext = os.path.splitext(filename)[1]
        if ext in self.video_exts:
            return True
        return False
    
    def get_files(self, path):
        file_paths = []
        for root, dirs, files in walklevel(path, 2):
            for file in files:
                if not self.is_videofile(file):
                    continue
                # filter small video
                if os.path.getsize(os.path.join(root, file)) < self.min_video_size:
                    continue
                
                # short name video
                if len(file)<=8:
                    continue
                file_path = os.path.join(root, file)
                file_paths.append(os.path.relpath(file_path, self.ARGS.media_src))
        
        delete_path = []
        for file_path, meta in self.cache.items():
            if file_path not in file_paths: # database have excess file
                # delete link
                if 'link_relpath' in meta:
                    link_path_old = os.path.join(self.ARGS.link_dst, meta['link_relpath'])
                    if os.path.exists(link_path_old) or \
                       os.path.islink(link_path_old): # link broken
                        logging.info(f"Remove: {os.path.relpath(link_path_old, self.ARGS.link_dst)}")
                        self.delete_related_file(link_path_old, meta['type'])
                delete_path.append(file_path)
        # delete the excess file in database
        for file_path in delete_path:
            del self.cache[file_path]
        
        return file_paths

    def ignore_files(self, file_paths): 
        # create default ignore file
        ignorefile_path = os.path.join(self.ARGS.media_src, self.ARGS.ignore_rule)
        if not os.path.exists(ignorefile_path):
            with open(ignorefile_path, 'w', encoding='utf-8') as f:
                f.write('/Sample\n')
                f.write('/SP\n')     # SPs, SP DISK
                f.write('Extras/\n')
        ignorer = IgnoreMatcher(ignorefile_path)
        
        # filter files
        filter_files = []
        for file_path in file_paths:
            if ignorer.is_ignored(file_path):
                logging.debug(f"Ignore: {file_path}")
                # check database if already linked
                if file_path in self.cache:
                    logging.info(f"cache ignore: {file_path}")
                    # if already linked, remove
                    if 'link_relpath' in self.cache[file_path]:
                        link_path_old = os.path.join(self.ARGS.link_dst, self.cache[file_path]['link_relpath'])
                        if os.path.exists(link_path_old):
                            logging.info(f"Remove: {os.path.relpath(link_path_old, self.ARGS.link_dst)}")
                            self.delete_related_file(link_path_old, self.cache[file_path]['type'])
                    # rm cache entry
                    del self.cache[file_path]
                continue
            filter_files.append(file_path)
        
        return filter_files

    def link(self, src, dst):
        if self.ARGS.dryrun:
            return
        if self.ARGS.symbol_link:
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst)
        else:
            os.link(src, dst)
    
    def delete_related_file(self, file_path, type):
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
        
        if not os.path.exists(file_path):
            return
        
        os.remove(file_path)
        
        if type == 'movie':
            dirpath = os.path.join(file_path, "..")
        else:
            dirpath = os.path.join(file_path, "../../")
        dirpath = os.path.abspath(dirpath)
        
        if check_empty(dirpath):
            logging.info(f"Remove dir: {os.path.relpath(dirpath, self.ARGS.link_dst)}")
            delete_dir(dirpath)
        
    def read_database(self):
        cache = {}
        cache_path = os.path.join(self.ARGS.media_src, 'cache.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        
        self.cache = cache
    
    def save_database(self):
        cache_path = os.path.join(self.ARGS.media_src, 'cache.json')
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2, default=str)
    
    def clear_miss_files(self):
        self.miss_title_files = []
        self.miss_ep_files = []
        self.miss_type_files = []
        
    def parse_filename_guessit(self, filename):
        from guessit import guessit
        
        # output = self.run_cmd(f'guessit "{filename}"')
        # m = re.search(r'{.*}', output, re.M |re.DOTALL)
        # if not m:
        #     return None
        # meta = json.loads(m.group(0))
        # return meta
        meta = guessit(filename)
        return dict(meta)
    
    # def parse_filename_gpt(self, filename):
    #     from Spark.Spark_parser import get_metadata
    #     meta = get_metadata([filename])
        
    def get_meta(self, file_path):
        filename = os.path.basename(file_path)
        meta = self.parse_filename_guessit(filename)
        # clear failed flag
        meta['failed'] = 0
        
        # return value
        '''code
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
        
        # try fix: title -> type -> episode -> season
        def try_fix():
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
                    self.miss_title_files.append({file_path:meta})
                    code, msg = 2, "miss title"
                    return
            
            # type not consistent
            if meta['type'] != self.ARGS.type:
                # have ep and no year
                if re.search(r'\b\d{1,2}\b', filename) and \
                    not re.search(r'\b\d{4}\b', filename):
                    meta['type'] = 'episode'
                else:
                    self.miss_type_files.append({file_path:meta})
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
                    meta_new = self.parse_filename_guessit(filename_)
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
                    return
                # season in title
                m = re.search(r'(2nd Season)|(II)', meta['title'], re.I)
                if m:
                    meta['season'] = 2
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    return
                m = re.search(r'(3rd Season)|(III)', meta['title'], re.I)
                if m:
                    meta['season'] = 3
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    return
                # title - 2$
                if re.search(r'[\s_-]\d{1}$', meta['title']):
                    meta['season'] = int(meta['title'][-1])
                    meta['title'] = meta['title'][:-1].strip()
                    return
                # simple fix
                meta['season'] = 1
                code = 1
            
            if self.ARGS.type == 'episode':
                if 'episode' not in meta:
                    fix_episode()
                if type(meta['episode'])==list:
                    self.miss_ep_files.append({file_path:meta})
                    code, msg = 4, "miss episode"
                    return
                if 'season' not in meta:
                    fix_season()
        try_fix()
        meta['code'] = code
        return meta, code, msg

    def make_link(self, file_path, meta):
        # make up link path
        filename = os.path.basename(file_path)
        ext_name = os.path.splitext(filename)[1]
        m = re.search(r'\d{3,4}', meta['screen_size'])
        resolution_str = f".{m.group()}p" if m else ''
        if resolution_str not in ['.720p', '.1080p', '.2160p']:
            resolution_str = ''
        if meta['type'] == 'episode':
            # /link/TV/Title/Season 1/Title-S01E01.2160p.mkv
            link_relpath = os.path.join(self.ARGS.tv_folder, meta['title'], f"Season {meta['season']}", f"{meta['title']}-S{meta['season']:02d}E{meta['episode']:02d}{resolution_str}{ext_name}")
        else: #movie
            # /link/Movie/Title (year)/Title (year).2160p.mkv
            year_str = f" ({meta['year']})" if meta['year'] else ''
            link_relpath = os.path.join(self.ARGS.movie_folder, f"{meta['title']}{year_str}", f"{meta['title']}{year_str}{resolution_str}{ext_name}")

        # already linked and not change dst
        if 'link_relpath' in meta and not self.ARGS.force_relink_check:
            # same link path, skip
            if meta['link_relpath'] == link_relpath:
                return
            # different, remove old and relink new
            link_path_old = os.path.join(self.ARGS.link_dst, meta['link_relpath'])
            self.delete_related_file(link_path_old, meta['type'])
        
        link_path = os.path.join(self.ARGS.link_dst, link_relpath)
        # link exists, skip
        if os.path.exists(link_path):
            meta['code'] = 9  # link exists
            return
        
        # update meta
        meta['link_relpath'] = link_relpath
        
        # ensure the link dir exists
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        logging.info(f"{file_path:50} -> {link_relpath}")
        
        # symlink or hardlink to dest path
        self.link(os.path.join(self.ARGS.media_src, file_path), link_path)
    
    def process_movie(self, file_paths):
        for file_path in file_paths:
            # check cache
            if file_path in self.cache:
                logging.debug(f" Hit: {file_path}")
                continue
            
            # new file, parse filename
            meta, code, msg = self.get_meta(file_path)
            if msg != "ok": # parse failed
                logging.warning(f" {msg:10}: {file_path}")
                meta['failed'] = 1  # parse failed
            self.cache[file_path] = meta

    def abspath2relpath(self):
        db = {}
        for file_path, meta in self.cache.items():
            if file_path.startswith('/'):
                relpath = os.path.relpath(file_path, self.ARGS.media_src)
                db[relpath] = meta
            else:
                db[file_path] = meta
        self.cache = db

    def pal(self, argv=None, options=None):
        self.set_argparser()
        if options is None:
            args = self.parser.parse_args(argv)
        else:
            args = self.load_args_dicts(options)
        self.process_args(args)
        self.run()
    
    def run(self):
        # read database(can be empty), self.cache
        self.read_database()
        # self.abspath2relpath()
        
        # traverse the src dir, get all filenames
        file_paths = self.get_files(self.ARGS.media_src)
        
        # filter files according ignore rules
        file_paths = self.ignore_files(file_paths)
        
        # miss list record failed files
        self.clear_miss_files()
        
        # after process, cache is dict of {file_path:meta}
        if self.ARGS.type == 'movie':
            self.process_movie(file_paths)
        else:
            # self.process_tv(file_paths)
            self.process_movie(file_paths)
        
        # handle failed files
        with open(self.ARGS.failed_json, 'w', encoding='utf-8') as f:
            json.dump({'miss_title_files':self.miss_title_files,
                       'miss_ep_files':self.miss_ep_files,
                       'miss_type_files':self.miss_type_files
                       }, f, ensure_ascii=False, indent=2, default=str)
        
        # according to new database, make link
        for file_path, meta in self.cache.items():
            if 'failed' not in meta:
                meta['failed'] = 0  # delete failed flag when handing failed files
            if meta['failed'] == 1: # failed meta, skip
                continue
            self.make_link(file_path, meta)
        
        # save cache
        self.save_database()

if __name__ == '__main__':
    pal = PaL()
    pal.pal()