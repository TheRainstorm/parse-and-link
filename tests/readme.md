## setup_test.py

`setup_test.py` is used to create a test media library conaining many movies and TV episodes.

Create a test `MediaLib/TV_Anime` directory containing all animes in json file
```bash
python tests/setup_test.py -j tests/example.TV_Anime.py.json -d MediaLib/TV_Anime
```

read all files in source directory and generate json file
```bash
python tests/setup_test.py -j tests/example.Movie_anime.py.json -s /mnt/Disk2/BT/downloads/Video/Movie_anime
```