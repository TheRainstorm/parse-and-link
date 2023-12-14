import fnmatch
import os

class IgnoreMatcher:
    def __init__(self, ignorefile_path):
        with open(ignorefile_path, 'r') as f:
            lines = f.readlines()
        self.ignore_rules = [line.strip() for line in lines if line.strip() and not line.startswith('#')]

    def is_ignored(self, path):
        for rule in self.ignore_rules:
            if rule.startswith('!'):  # Reverse match
                if rule[1:] in path:
                    return False
            elif rule in path:
                return True
        return False

    def filter_files(self, path_list):
        return [path for path in path_list if not self.is_ignored(path)]

if __name__ == '__main__':
    # Example usage:
    gitignore_path = '/mnt/Disk2/BT/downloads/Video/Movie_anime/skip.txt'
    matcher = IgnoreMatcher(gitignore_path)

    for root, dirs, files in os.walk('/mnt/Disk2/BT/downloads/Video/Movie_anime'):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext not in ['.mkv', '.mp4', '.avi']:
                continue
            # video file
            file_path = os.path.join(root, file)
            if matcher.is_ignored(file_path):
                print(f"Skip: {file_path}")