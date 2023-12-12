import os
import argparse
import logging
import re
import json
import subprocess
import shlex

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
        parser.add_argument('--skip-dir',
                            default="skip.txt",
                            help='file contain excule dirname, one dirname per line.')
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
        parser.add_argument('--cache',
                            action='store_true',
                            default=True,
                            help='cache parsed metadata to json file in media_src/cache.json')
        parser.add_argument('--save-link',
                            action='store_true',
                            default=True,
                            help='logging link mapping in link_dst/links.log')
        # given the IMDb id, no need to parse from filename. working with other frontend tools
        parser.add_argument('--imdbid',
                            default='',
                            help='specify the IMDb id, -s single mode only')
        parser.add_argument('--tmdbid',
                            default='',
                            help='specify the TMDb id, -s single mode only')
        parser.add_argument('--after-copy-script',
                            default='',
                            help='call this script with destination folder path after link/move')

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
        
        # skip
        if self.ARGS.skip_dir:
            skip_file_path = os.path.join(self.ARGS.media_src, self.ARGS.skip_dir)
            if not os.path.exists(skip_file_path):
                with open(skip_file_path, 'w', encoding='utf-8') as f:
                    f.write('/Samples/\n')
                    f.write('/SPs/\n')
            with open(skip_file_path, 'r', encoding='utf-8') as f:
                self.skip_dirnames = f.read().splitlines()
    
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
                file_paths.append(os.path.join(root, file))
        return file_paths
    
    def run_cmd(self, cmd):
        output = subprocess.run(shlex.split(cmd), capture_output=True).stdout.decode('utf-8')
        return output

    def link(self, src, dst):
        if self.ARGS.dryrun:
            return
        if self.ARGS.symbol_link:
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst)
        else:
            os.link(src, dst)
    
    def get_meta_guessit(self, file_path):
        filename = os.path.basename(file_path)
        output = self.run_cmd(f'guessit "{filename}"')
        m = re.search(r'{.*}', output, re.M |re.DOTALL)
        if not m:
            logging.error(f'failed to parse {filename}')
            return None, "failed to parse"
        meta = json.loads(m.group(0))
        
        # check meta
        if 'season' not in meta:
            meta['season'] = 1
        if 'screen_size' not in meta:
            meta['screen_size'] = ''
        
        # failed to parse, save to failed list
        if 'title' not in meta:
            self.miss_title_files.append({file_path:meta})
            return None, "miss title"
        
        # if meta type is not same as ARGS.type
        if meta['type'] != self.ARGS.type:
            self.miss_type_files.append({file_path:meta})
            return None, "miss type"
        
        if self.ARGS.type == 'episode':
            if 'episode' not in meta:
                meta['episode'] = []
            if type(meta['episode'])==list:
                self.miss_ep_files.append({file_path:meta})
                return None, "miss episode"
        
        return meta, "ok"
        
    def main(self, argv=None):
        self.load_args(argv)
        
        # traverse the src dir, get all filenames
        file_paths = self.get_files(self.ARGS.media_src)
        
        # check cache
        cache_path = os.path.join(self.ARGS.media_src, 'cache.json')
        if self.ARGS.cache and os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        else:
            cache = {}
        
        # logging link mapping
        link_file = open(os.path.join(self.ARGS.link_dst, 'links.log'), "a")
        
        # save miss parse files
        self.miss_title_files = []
        self.miss_ep_files = []
        self.miss_type_files = []
        
        # for each file, parse the filename, get the metadata, and link to dest path
        for file_path in file_paths:
            # skip dirname
            for dirname in self.skip_dirnames:
                if dirname in file_path:
                    logging.info(f"Skip: {os.path.relpath(file_path, self.ARGS.media_src)}")
                    continue
                
            # cached file, skip
            if file_path in cache:
                meta = cache[file_path]
                logging.info(f" Hit: {os.path.relpath(file_path, self.ARGS.media_src)}")
                if meta['link_dst'] == self.ARGS.link_dst:
                    continue
            else:
                meta, msg = self.get_meta_guessit(file_path)
                if meta is None:
                    logging.warning(f" {msg:10}: {os.path.relpath(file_path, self.ARGS.media_src)}")
                    continue
            
            # make up link path
            filename = os.path.basename(file_path)
            ext_name = os.path.splitext(filename)[1]
            m = re.search(r'\d{3,4}', meta['screen_size'])
            resolution_str = f".{m.group()}p" if m else ''
            # resolution_str = '' if resolution_str == '.1080p' else resolution_str  # 1080p is default, no need to add to link path
            if meta['type'] == 'episode':
                # /link/TV/Title/Season 1/Title-S01E01.2160p.mkv
                link_path = os.path.join(self.ARGS.link_dst, self.ARGS.tv_folder, meta['title'], f"Season {meta['season']}", f"{meta['title']}-S{meta['season']:02d}E{meta['episode']:02d}{resolution_str}{ext_name}")
            elif meta['type'] == 'movie':
                # /link/Movie/Title (year)/Title (year).2160p.mkv
                year_str = f" ({meta['year']})" if meta['year'] else ''
                link_path = os.path.join(self.ARGS.link_dst, self.ARGS.movie_folder, meta['title'], f"{meta['title']} ({meta['year']}){resolution_str}{ext_name}")
            
            # link exists, skip
            if os.path.exists(link_path):
                continue
            
            # ensure the link dir exists
            os.makedirs(os.path.dirname(link_path), exist_ok=True)
            logging.info(f"{os.path.relpath(file_path, self.ARGS.media_src):50} -> {os.path.relpath(link_path, self.ARGS.link_dst)}")
            
            # symlink or hardlink to dest path
            self.link(file_path, link_path)
            
            # cache
            meta['link_dst'] = self.ARGS.link_dst  # add link_dst to meta
            meta['link_rel_path'] = os.path.relpath(link_path, self.ARGS.link_dst)
            cache[file_path] = meta
            
            # save link mapping
            if self.ARGS.save_link:
                link_file.write(f"{os.path.relpath(file_path, self.ARGS.media_src):50} -> {os.path.relpath(link_path, self.ARGS.link_dst)}\n")
        
        # handle failed files
        with open('failed.json', 'w', encoding='utf-8') as f:
            json.dump({'miss_title_files':self.miss_title_files,
                       'miss_ep_files':self.miss_ep_files,
                       'miss_type_files':self.miss_type_files
                       }, f, ensure_ascii=False, indent=2)
        
        link_file.close()
        
        # save cache
        if self.ARGS.cache:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    pal = PaL()
    pal.main()