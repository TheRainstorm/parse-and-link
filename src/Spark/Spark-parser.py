import SparkApi
import os

# 密钥信息从讯飞星火网站控制台获取
# 添加到环境变量中
appid = os.environ.get("APPID")
api_secret = os.environ.get("API_SCERET")
api_key = os.environ.get("API_KEY")

domain = "generalv3"
Spark_url = "ws://spark-api.xf-yun.com/v3.1/chat"

import pickle
import json
import re

def load_obj(pklfile):
    with open(pklfile, 'rb') as f:
        obj = pickle.load(f)
    return obj

def dump_obj(obj, pklfile):
    with open(pklfile, 'wb') as f:
        pickle.dump(obj, f)
                    
def get_metadata(filename_list):
    filenames = ','.join(filename_list)
    text = [
        {"role": "system", "content": "You are a helpful assistant, skilled in extracting metadata from video filename and return json data."},
        {"role": "user", "content": f"extract video metadata from filename list [{filenames}], return json including keys: title, season, episode, video_codec, screen_size, audio_codec, release_group, container, type(episode or movie)"}
    ]
    text2 = [
        {"role": "system", "content": "You are a helpful assistant, skilled in extracting metadata from video filename and return json data."},
        {"role": "user", "content": f"Extract metadata from filename list and return list of dict in json, dict keys including: title, season, episode, video_codec, screen_size, audio_codec, release_group, container, type(episode or movie). Filename list is: {filenames}, answer must is valid json format"}
    ]

    SparkApi.answer =""
    SparkApi.main(appid,api_key,api_secret,Spark_url,domain,text2)
    
    metadata = None
    m = re.search(r'\[.*\]', SparkApi.answer, re.M |re.DOTALL)
    if m:
        metadata = json.loads(m.group())
    return metadata, SparkApi.answer

if __name__ == "__main__":
    TV_anime_list = [
        "[Sakurato] Kage no Jitsuryokusha ni Naritakute! S2 [01][HEVC-10bit 1080P AAC][CHS&CHT].mkv",
        "[Sakurato] Spy x Family Season 2 [04][HEVC-10bit 1080p AAC][CHS&CHT].mkv",
        "[BeanSub&FZSD][Kimetsu_no_Yaiba][49][GB][1080P][x264_AAC].mp4",
        "[Nekomoe kissaten&VCB-Studio] takt op.Destiny [CM][Ma10p_1080p][x265_flac].mkv",
        "[Neon Genesis Evangelion][15][BDRIP][1440x1080][H264_FLACx2].mkv",
        "[Neon Genesis Evangelion][Vol.09][SP04][NCED][BDRIP][1440x1080][H264_FLAC].mkv",
    ]

    movie_list = [
        "[穿越时空的少女].The.Girl.Who.Leapt.Through.Time.TWN.2006.BluRay.1080p.x264.AC3.2Audios-CMCT.mkv",
        "My Neighbors the Yamadas 1999 720p BluRay DD5.1 x264-CtrlHD.mkv",
        "[ANK-Raws] 西游记之大圣归来 (BDrip 1920x1080 HEVC-YUV420P10 FLAC DTS-HDMA SUP).mkv",
        "[Evangelion 3.0+1.11 Thrice Upon a Time][Tokuten BD][SP21][3.333 Trailer Updated #03][BDRIP][1920x1080][H264_FLAC].mkv",
        "[Evangelion 3.33 You Can (Not) Redo.][SP13][EVA-Extra][BDRIP][1080P][H264_FLAC].mkv",
        "秒速5厘米 轨迹照片回顾.mkv"
    ]

    filename_list = movie_list

    metadata, _ = get_metadata(filename_list)
    # metadata = load_obj("metadata.pkl")

    from pprint import pprint
    for filename, meta in zip(filename_list, metadata):
        print(filename)
        pprint(meta)
        print()

    dump_obj(metadata, "metadata.pkl")