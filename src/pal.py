import os
import argparse
import logging
import re
import json

from walklevel import walklevel

class PaL:
    def __init__(self):
        self.ARGS = None
        self.video_exts = ['.mkv', '.mp4', '.avi']
        self.min_video_size = 100*1024*1024 # 100MB
        self.skip_dirnames = []
    
    def load_args(self, argv=None):
        parser = argparse.ArgumentParser(
            description='ProjectName: parse Movie and TV file metadata, then link to dest path.'
        )
        parser.add_argument('-s',
                            '--media-src',
                            required=True,
                            help='The directory contains TVs and Movies to be copied.')
        parser.add_argument('-d',
                            '--link-dst',
                            required=True,
                            help='the dest path to create Link.')
        # parser.add_argument('--tmdb-api-key',
        #                     # required=True,
        #                     help='Search API for the tmdb id, and gen dirname as Name (year)\{tmdbid=xxx\}')
        parser.add_argument('-S',
                            '--symbol-link',
                            action='store_true',
                            help='symbol link')
        # parser.add_argument('--only-link',
        #                     action='store_true',
        #                     help='don\'t save .nfo file in the media dir')
        parser.add_argument('-t',
                            '--type',
                            type=int,
                            required=True,
                            help='0: tv, 1: movie. specify the src directory is TV or Movie, default TV.')
        parser.add_argument('--tv-folder',
                            default="TV",
                            help='specify the name of TV directory, default TV.')
        parser.add_argument('--movie-folder',
                            default="Movie",
                            help='specify the name of Movie directory, default Movie.')
        parser.add_argument('--ignore-rule',
                            default="skip.txt",
                            help='one rule per line, string ignore a directory or file, \
                                `!` cancel ignore(place before direcotry ignore rule)')
        parser.add_argument('--keep-sub',
                            action='store_true',
                            help='keep files with these extention(\'srt,ass\').')
        parser.add_argument('--dryrun',
                            action='store_true',
                            help='print message instead of real copy.')
        parser.add_argument('--make-log',
                            action='store_true',
                            help='Make a log file.')
        parser.add_argument('--loglevel',
                            default='INFO',
                            help='--log=DEBUG, INFO, WARNING, ERROR, CRITICAL')
        parser.add_argument('--change-dst',
                            action='store_true',
                            help='set true when link src to new dst, affect cache')
        parser.add_argument('--failed-json',
                            default='failed.json',
                            help='specify the file path to save failed result, default "failed.json"')
        # parser.add_argument('--imdbid',
        #                     default='',
        #                     help='specify the IMDb id')
        # parser.add_argument('--tmdbid',
        #                     default='',
        #                     help='specify the TMDb id')

        self.ARGS = parser.parse_args(argv)
        self.ARGS.media_src = os.path.expanduser(self.ARGS.media_src)
        self.ARGS.link_dst = os.path.expanduser(self.ARGS.link_dst)
        os.makedirs(self.ARGS.link_dst, exist_ok=True)

        # logging
        numeric_level = getattr(logging, self.ARGS.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % self.ARGS.loglevel)
        if self.ARGS.make_log:
            logging.basicConfig(filename='pal.log', level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        else:
            logging.basicConfig(level=numeric_level,
                                format='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
        
        # check type
        self.ARGS.type = 'episode' if self.ARGS.type == 0 else 'movie'
    
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
                file_paths.append(os.path.join(root, file))
        
        # delete the extra entry in database
        delete_path = []
        for file_path, meta in self.cache.items():
            if file_path not in file_paths:
                # delete link file
                if 'link_relpath' in meta:
                    link_path_old = os.path.join(self.ARGS.link_dst, meta['link_relpath'])
                    if os.path.exists(link_path_old) or \
                       os.path.islink(link_path_old): # link broken
                        logging.info(f"Remove: {os.path.relpath(link_path_old, self.ARGS.link_dst)}")
                        self.remove_dir(link_path_old)
                delete_path.append(file_path)
        for file_path in delete_path:
            del self.cache[file_path]
        
        return file_paths

    def add_ignore_rule(self, rule):
        ignorefile_path = os.path.join(self.ARGS.media_src, self.ARGS.ignore_rule)
        with open(ignorefile_path, 'a', encoding='utf-8') as f:
            f.write(rule+'\n')
            
    def ignore_files(self, file_paths):
        from ignore_matcher import IgnoreMatcher
        
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
            relpath = os.path.relpath(file_path, self.ARGS.media_src)
            if ignorer.is_ignored(relpath):
                logging.debug(f"Ignore: {relpath}")
                # check database
                if file_path in self.cache:
                    logging.info(f"cache ignore: {relpath}")
                    # if already linked, remove
                    if 'link_relpath' in self.cache[file_path]:
                        link_path_old = os.path.join(self.ARGS.link_dst, self.cache[file_path]['link_relpath'])
                        if os.path.exists(link_path_old):
                            logging.info(f"Remove: {os.path.relpath(link_path_old, self.ARGS.link_dst)}")
                            self.remove_dir(link_path_old)
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
    
    def remove_dir(self, file_path):
        os.remove(file_path)
        # remove empty dir
        dirpath = os.path.dirname(file_path)
        for file in os.listdir(dirpath):
            ext = os.path.splitext(file)[1]
            if ext not in ['.nfo', '.jpg', '.png']:
                # not empty, can't delete dir
                return
        for file in os.listdir(dirpath):
            os.remove(os.path.join(dirpath, file))
        os.rmdir(dirpath)
        
    def read_database(self):
        cache = {}
        cache_path = os.path.join(self.ARGS.media_src, 'cache.json')
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        
        self.cache = cache
        return cache
    
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
        # del object key
        if 'country' in meta:
            del meta['country']
        if 'language' in meta:
            del meta['language']
        return dict(meta)
    
    # def parse_filename_gpt(self, filename):
    #     from Spark.Spark_parser import get_metadata
    #     meta = get_metadata([filename])
        
    def get_meta(self, file_path):
        filename = os.path.basename(file_path)
        meta = self.parse_filename_guessit(filename)
        
        # clear failed flag
        meta['failed'] = 0
        
        code = 0
        # check meta
        if 'screen_size' not in meta:
            meta['screen_size'] = ''
        if 'year' not in meta:
            meta['year'] = ''
        
        # failed to parse, save to failed list
        if 'title' not in meta:
            # fix title
            fixed = False
            if re.match(r'^(\[[^\]]+\])+(\(.*\))?\..*$', filename): # [xxx][title][xxx].mkv
                parts = re.split(r'\[|\]', filename)
                filename = max(parts, key=len)
                filename = filename.strip().replace('_', ' ')
                meta['title'] = filename
                fixed = True
                # meta_new = self.parse_filename_guessit(filename_sub)
                # if 'title' in meta_new:
                #     meta['title'] = meta_new['title']
            if not fixed:
                self.miss_title_files.append({file_path:meta})
                meta['code'] = 2
                return meta, 2, "miss title"
        
        # if meta type is not same as ARGS.type
        if meta['type'] != self.ARGS.type:
            if re.search(r'\b\d{1,2}\b', filename) and \
                not re.search(r'\b\d{4}\b', filename):
                meta['type'] = 'episode'
            else:
                self.miss_type_files.append({file_path:meta})
                meta['code'] = 3
                return meta, 3, "miss type"
        
        if self.ARGS.type == 'episode':
            if 'episode' not in meta:
                # [01]
                m = re.search(r'\[(\d{2})\]', filename)
                if m:
                    ep = int(m.group(1))
                    filename = filename.replace(m.group(0), '')
                    # reparse, may fix season
                    meta_new = self.parse_filename_guessit(filename)
                    meta['episode'] = ep
                    if 'season' in meta_new:
                        meta['season'] = meta_new['season']
                # - 9
                elif re.search(r'\b\d{1,2}\b', filename):
                    m = re.search(r'\b(\d{1,2})\b', filename)
                    meta['episode'] = int(m.group(1))
                else:
                    meta['episode'] = []
            if type(meta['episode'])==list:
                self.miss_ep_files.append({file_path:meta})
                meta['code'] = 4
                return meta, 4, "miss episode"
            
            # season fix
            if 'season' in meta and type(meta['season'])==list:
                meta['code'] = 5
                return meta, 5, "bad season"
            
            # season in title
            if 'season' not in meta:
                if re.search(r'(2nd Season)|(II)', meta['title'], re.I):
                    meta['season'] = 2
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    
                elif re.search(r'(3rd Season)|(III)', meta['title'], re.I):
                    meta['season'] = 3
                    meta['title'] = meta['title'].replace(m.group(0), '').strip()
                    
                elif re.search(r'[\s_-]\d{1}$', meta['title']):
                    meta['season'] = int(meta['title'][-1])
                    meta['title'] = meta['title'][:-1].strip()
                
                else:
                    meta['season'] = 1
                    code = 1

        return meta, code, "ok"

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
        elif meta['type'] == 'movie':
            # /link/Movie/Title (year)/Title (year).2160p.mkv
            year_str = f" ({meta['year']})" if meta['year'] else ''
            link_relpath = os.path.join(self.ARGS.movie_folder, f"{meta['title']}{year_str}", f"{meta['title']}{year_str}{resolution_str}{ext_name}")

        # already linked and not change dst
        if 'link_relpath' in meta and not self.ARGS.change_dst:
            # same link path, skip
            if meta['link_relpath'] == link_relpath:
                return
            # different, remove old and relink new
            link_path_old = os.path.join(self.ARGS.link_dst, meta['link_relpath'])
            if os.path.exists(link_path_old):
                logging.info(f"Remove: {os.path.relpath(link_path_old, self.ARGS.link_dst)}")
                self.remove_dir(link_path_old)
        
        # update meta
        meta['link_relpath'] = link_relpath
        
        link_path = os.path.join(self.ARGS.link_dst, link_relpath)
        # link exists, skip
        if os.path.exists(link_path):
            return
        
        # ensure the link dir exists
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        logging.info(f"{os.path.relpath(file_path, self.ARGS.media_src):50} -> {os.path.relpath(link_path, self.ARGS.link_dst)}")
        
        # symlink or hardlink to dest path
        self.link(file_path, link_path)
    
    def process_movie(self, file_paths, cache):
        for file_path in file_paths:
            # check cache
            if file_path in cache:
                logging.debug(f" Hit: {os.path.relpath(file_path, self.ARGS.media_src)}")
                continue
            
            # new file, parse filename
            meta, code, msg = self.get_meta(file_path)
            if msg != "ok": # parse failed
                logging.warning(f" {msg:10}: {os.path.relpath(file_path, self.ARGS.media_src)}")
                meta['failed'] = 1  # parse failed
            cache[file_path] = meta

    def main(self, argv=None):
        self.load_args(argv)
        
        # get cache(can be empty)
        cache = self.read_database()
        
        # traverse the src dir, get all filenames
        file_paths = self.get_files(self.ARGS.media_src)
        
        # check ignore rule
        file_paths = self.ignore_files(file_paths)
        
        # miss list record failed files
        self.clear_miss_files()
        
        # after process, cache is dict of {file_path:meta}
        if self.ARGS.type == 'movie':
            self.process_movie(file_paths, cache)
        else:
            # self.process_tv(file_paths, cache)
            self.process_movie(file_paths, cache)
        
        # handle failed files
        with open(self.ARGS.failed_json, 'w', encoding='utf-8') as f:
            json.dump({'miss_title_files':self.miss_title_files,
                       'miss_ep_files':self.miss_ep_files,
                       'miss_type_files':self.miss_type_files
                       }, f, ensure_ascii=False, indent=2, default=str)
        
        # according to new database, make link
        for file_path, meta in cache.copy().items():  # copy: fix dictionary changed size during iteration
            if 'failed' not in meta:
                meta['failed'] = 0  # delete failed flag, when handing failed files
            if meta['failed'] == 1: # failed meta, skip
                continue
            self.make_link(file_path, meta)
        
        # save cache
        self.save_database()

if __name__ == '__main__':
    pal = PaL()
    pal.main()