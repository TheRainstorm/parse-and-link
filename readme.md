## 说明

一个自动从源目录读取所有视频文件，提取出标题等元信息，然后按照规范格式链接到目标目录的工具，用于实现下载做种和媒体库刮削分离。格式目前适配jellyfin。

本项目是在已有项目上的极简实现
- [guessit](https://github.com/guessit-io/guessit): 可以从文件名尽可能提取所有元信息

基本假设
- 文件名一定包含标题
- 剧集文件名一定包含集数

## 背景

对于PT爱好者，通常已经收藏了丰富的电影、电视剧和动漫等资源，然而如何美观地展示它们是一个不太容易的事情。不过，市面上已经有一些方案可以让普通用户搭建出属于自己的视频网站或者说——个人媒体库。用户可以通过网页或者App的形式访问自己的媒体库。媒体库会展示海报墙、简介、标签、演员等丰富的信息，用户也能直接播放视频。通常来说收集的数据越多，展示的海报墙就越漂亮，因此这对PT爱好者简直有无穷的吸引力。

目前的方案可以分为商业成熟的方案和个人DIY的方案。商业的方案比如苹果的Infuse软件，用户仅需要指定媒体的存储位置（支持smb），软件便会自动搜索识别整理媒体资源并在多端同步（比如Apple TV）。另一个比较成功的商业产品形态便是作为NAS产品系统软件的一部分，现有各种nas产品通常都会包含一个集成的影音中心。并且该软件的易用性通常可以作为NAS产品亮点的一部分。

个人DIY的方案最有名的便是开源软件jellyfin，社区非常活跃。值得一提的是jellyfin是基于Emby软件发展而来的，而Emby是一个商业软件，需要付费订阅。二者各有优缺，看个人喜好选择。本文接下来探讨的主要是jellyfin。

个人媒体库软件的挑战之一便是从五花八门的视频文件名称中识别出正确的电影电视名称，然后从媒体网站下载对应的封面、简介等元数据。该过程通常也被称为刮削。
虽然jellyfin仍然在活跃开发中，但是目前从视频文件名识别信息这一点做的并不好。而一旦识别不正确，媒体库的海报墙便会显示缺失的图片，动漫番剧更是这里缺一集那里缺一集。许多同类软件也都面临相同问题。

对于用户来说，一个解决方案便是使用单独的工具进行刮削。tmm便是一个使用广泛的工具，支持图形化的界面，在无法自动识别时可以手动进行设置。使用该工具已经能够解决许多问题了，最差情况下便是需要花费很多时间在手动整理未识别的视频上（通常是电视剧集数信息）

然而对于PT爱好者来说，还有一个挑战是下载的资源通常还希望继续做种，因此通常不希望对资源进行重命名或者移动。因此最好是下载目录和识别目录进行分离。围绕该思路有一些工具，其中值得一提的是nas-tool，该软件可以识别视频信息，并将其链接到另一个目录，同时进行重命名。重命名后的目录、文件名都是遵循一定格式的，因此非常整洁。使用链接目录作为jellyfin的媒体路径时便基本能达到100%的准确度了，已经属于好用的程度。

然而nas-tool自身的识别正确率却依然不高，刮削链接功能只是该项目功能之一，其还包含自动订阅下载，刷流等其它繁杂功能。对于我来说，识别准确的重要性是最重要的，对于如今chatgpt都被宣传为要超越人类了，而如此直觉上简单的功能却这么多工具都做不好对我来说还是挺意外的。而且上述工具均无法让用户简单的修改其识别逻辑。

因此我想要围绕刮削+链接，自己实现一个工具，目标是实现接近完美的刮削效果。该工具的特点为：
- 软连接模式：适用于想保留原始做种文件的用户，这是因为一些BD资源，除了视频通常也包含一些音频和图片，而这些资源是没办法被jellyfin等软件展示的，因此通常不会被刮削
  - 优点：
    - 支持**多块做种盘**文件链接到一个路径（避免需要在jellyfin里反复
    - 保留BDrip完整数据，适用于收藏党
    - 可以把链接完全作为额外数据进行复制（硬链接rsync时更麻烦些）
  - 缺点
    - 删除链接后，需要重新刮削（也就是说只需要能够快速准确刮削，就没有缺点）
- 硬链接模式：刮削完成后，通常会删除做种文件的用户
  - 优点
    - 保留的数据非常规整
  - 缺点
    - 丢失BD其它数据
- 使用各种复杂算法，强化识别准确率（许多动漫仅是使用`xxx [01] xxx`这样的方式包含集数信息，现有的工具竟然都无法识别）
  - 使用AI算法，提取关键字
  - 最使用chatgpt API识别

## 使用

### 识别错误后处理

**手动设置title等信息**

手动修改源目录的数据文件`cache.json`
- 对于识别不正确的，修改title即可
- 对于识别失败的(`failed=1`)，设置好title后，删除`failed`字段

重新运行程序，程序会删除原本链接，然后生成新连接。

例子：
```json
"/mnt/Disk2/BT/downloads/Video/Movie_anime/穿越时空的少女.2006.TWN.1080p.中日双语.简繁中字￡CMCT利姆鲁/[穿越时空的少女].The.Girl.Who.Leapt.Through.Time.TWN.2006.BluRay.1080p.x264.AC3.2Audios-CMCT.mkv": {
    "title": "The Girl Who Leapt Through Time TWN",
    "year": 2006,
    "source": "Blu-ray",
    "screen_size": "1080p",
    "video_codec": "H.264",
    "audio_codec": "Dolby Digital",
    "release_group": "2Audios-CMCT",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "movie",
    "failed": 0,
    "season": 1,
    "relpath": "Movie_anime/The Girl Who Leapt Through Time TWN/The Girl Who Leapt Through Time TWN (2006).1080p.mkv"
  },
```
删除导致jellyfin无法识别的标题中的"TWN"后，重新运行程序。可以看到日志输出了删除旧链接，创建新链接的路径。
```bash
2023-12-14 14:01:00 INFO Remove: Movie_anime/The Girl Who Leapt Through Time TWN/The Girl Who Leapt Through Time TWN (2006).1080p.mkv
2023-12-14 14:01:00 INFO 穿越时空的少女.2006.TWN.1080p.中日双语.简繁中字￡CMCT利姆鲁/[穿越时空的少女].The.Girl.Who.Leapt.Through.Time.TWN.2006.BluRay.1080p.x264.AC3.2Audios-CMCT.mkv -> Movie_anime/The Girl Who Leapt Through Time/The Girl Who Leapt Through Time (2006).1080p.mkv
```

**忽略文件**

对于一些不必要的文件，可以在`skip.txt`中添加忽略规则，程序会忽略这些文件，并从数据库中删除。

规则文件格式：
- 一行一个规则，`#`开始的为注释。
- 规则指定了需要忽略的模式，文件路径包含模式字符串则会被忽略
- `!`反向匹配，即不忽略

```
/Sample
/SP
Extras/
![Evangelion 3.0+1.11 Thrice Upon a Time][JPN][BDRIP][1920x816][H264_FLACx3].mkv
![Evangelion 3.33 You Can (Not) Redo.][JPN][BDRIP][1920x816][H264_FLACx2].mkv
![Evangelion 2.22 You Can (Not) Advance][JPN][BDRIP][1080P][H264_AC3_DTS-HDMA].mkv
![Evangelion 1.11 You Are (Not) Alone][BDRIP][1080P][H264_AC3_DTS-HDMA].mkv
Evangelion Shin Gekijouban 01-04/
```

示例输出
```
2023-12-14 15:54:51 INFO cache ignore: [ANK-Raws] 西游记之大圣归来 (BDrip 1920x1080 HEVC-YUV420P10 FLAC DTS-HDMA SUP)/「日本版予告編」.mkv
2023-12-14 15:54:51 INFO cache ignore: 5.Centimeters.Per.Second.2007.BluRay.1080p-ted423@FRDS/Extras/Makoto.Shinkai.interview.mkv
2023-12-14 15:54:51 INFO cache ignore: 5.Centimeters.Per.Second.2007.BluRay.1080p-ted423@FRDS/Extras/One.more.time,One.more.chance.mkv
2023-12-14 15:54:51 INFO Remove: Movie_anime/One more time,One more chance/One more time,One more chance ().mkv
```


## TODO

- [x] symlink和link完美替换
- [x] revese-link文件，记录链接文件原始路径
- [x] cache加速，将每个file_path: metadata记录到文件
- [x] 默认链接目录下子目录和src目录名一致。但是为了解决混合目录情况，必须同时指定tv,movie目录。
- [x] 错误处理，记录到日志文件。
- [ ] 剧集集数识别算法：按照title分组，组内不确定集数的filename，需要让整个group的缺失集数最少。（缺失集数：min-max中interval之和）
- [ ] 相似title合并，在剧集识别算法之前
- [ ] 使用GPT对识别错误的文件重新处理
- [ ] 复制原本存在的字幕文件

### 相似title合并

标题细微差别，但是被分为不同目录
```
[Nekomoe kissaten&LoliHouse] NieR Automata Ver1.1a - 01 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv -> TV_anime/NieR Automata Ver1 1a/Season 1/NieR Automata Ver1 1a-S01E01.1080p.mkv

[EMBER] NieR-Automata Ver1.1a - 02.mkv             -> TV_anime/NieR-Automata Ver1 1a/Season 1/NieR-Automata Ver1 1a-S01E02.mkv
```

### 识别错误

#### type识别错误

识别正确，但是和指定的类型不同
```
For: 向着明亮那方.To.the.Bright.Side.2022.1080p.WEB-DL.AAC2.0.H264-HDSWEB.mp4
GuessIt found: {
    "title": "向着明亮那方 To the Bright Side",
    "year": 2022,
    "screen_size": "1080p",
    "source": "Web",
    "audio_codec": "AAC",
    "audio_channels": "2.0",
    "video_codec": "H.264",
    "release_group": "HDSWEB",
    "container": "mp4",
    "mimetype": "video/mp4",
    "type": "movie"
}
```

识别错误
```
For: [Niconeiko Works] Kaguya-sama wa Kokurasetai First Kiss wa Owaranai [1080P_Ma10p_FLAC_DTS-HDMA][03].mkv
GuessIt found: {
    "release_group": "Niconeiko Works",
    "title": "Kaguya-sama wa Kokurasetai First Kiss wa Owaranai",
    "screen_size": "1080p",
    "audio_codec": [
        "FLAC",
        "DTS-HD"
    ],
    "audio_profile": "Master Audio",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "movie"
}
```

#### episode错误

集数信息识别不出
```
For: [Sakurato] Kage no Jitsuryokusha ni Naritakute! S2 [01][HEVC-10bit 1080P AAC][CHS&CHT].mkv
GuessIt found: {
    "title": "Kage no Jitsuryokusha ni Naritakute!",
    "season": 2,
    "video_codec": "H.265",
    "video_profile": "High Efficiency Video Coding",
    "color_depth": "10-bit",
    "screen_size": "1080p",
    "audio_codec": "AAC",
    "release_group": "CHS&CHT",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

集数信息识别错误，得到一个列表
```
For: [Nekomoe kissaten&LoliHouse] Zom 100 - Zombie ni Naru made ni Shitai 100 no Koto - 06 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv
GuessIt found: {
    "title": "Zom",
    "episode": [
        100,
        6
    ],
    "episode_title": "Zombie ni Naru made ni Shitai",
    "source": "Web",
    "other": "Rip",
    "screen_size": "1080p",
    "video_codec": "H.265",
    "video_profile": "High Efficiency Video Coding",
    "color_depth": "10-bit",
    "audio_codec": "AAC",
    "release_group": "ASSx2",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

#### title错误

标题识别不出
```
For: [BeanSub&FZSD][Kimetsu_no_Yaiba][49][GB][1080P][x264_AAC].mp4
GuessIt found: {
    "release_group": "BeanSub&FZSD",
    "episode": 49,
    "country": "UNITED KINGDOM",
    "screen_size": "1080p",
    "video_codec": "H.264",
    "audio_codec": "AAC",
    "container": "mp4",
    "mimetype": "video/mp4",
    "type": "episode"
}
```

标题缺失
```
For: Oshi no Ko [10][AVC-8bit 1080p AAC][CHS&JPN].mp4
GuessIt found: {
    "title": "Oshi no",
    "language": "Korean",
    "episode": 10,
    "video_codec": "H.264",
    "video_profile": "Advanced Video Codec High Definition",
    "color_depth": "8-bit",
    "screen_size": "1080p",
    "audio_codec": "AAC",
    "release_group": "CHS&JPN",
    "container": "mp4",
    "mimetype": "video/mp4",
    "type": "episode"
}
```

标题一部分被识别成可选标题
```
For: Nier - Automata Ver1.1a - S01E01 - or not to [B]e.mkv
GuessIt found: {
    "title": "Nier",
    "alternative_title": "Automata Ver1 1a",
    "season": 1,
    "episode": 1,
    "episode_title": "or not to",
    "release_group": "B",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

标题一部分被识别成集标题
```
For: [Nekomoe kissaten&LoliHouse] Zom 100 - Zombie ni Naru made ni Shitai 100 no Koto - 06 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv
GuessIt found: {
    "title": "Zom",
    "episode": [
        100,
        6
    ],
    "episode_title": "Zombie ni Naru made ni Shitai",
    "source": "Web",
    "other": "Rip",
    "screen_size": "1080p",
    "video_codec": "H.265",
    "video_profile": "High Efficiency Video Coding",
    "color_depth": "10-bit",
    "audio_codec": "AAC",
    "release_group": "ASSx2",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

#### season错误

季信息被识别成标题一部分
```
For: Kage no Jitsuryokusha ni Naritakute! 2nd Season [04][HEVC-10bit 1080p AAC][CHS&CHT].mkv
GuessIt found: {
    "title": "Kage no Jitsuryokusha ni Naritakute! 2nd Season",
    "episode": 4,
    "video_codec": "H.265",
    "video_profile": "High Efficiency Video Coding",
    "color_depth": "10-bit",
    "screen_size": "1080p",
    "audio_codec": "AAC",
    "release_group": "CHS&CHT",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}

For: [VCB-Studio] Sword Art Online II [14][Ma10p_1080p][x265_flac].mkv
GuessIt found: {
    "release_group": "VCB-Studio",
    "title": "Sword Art Online II",
    "episode": 14,
    "screen_size": "1080p",
    "video_codec": "H.265",
    "audio_codec": "FLAC",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

集数被识别成季信息
```
For: [Sakurato] Spy x Family Season 2 [04][HEVC-10bit 1080p AAC][CHS&CHT].mkv
GuessIt found: {
    "title": "Spy x Family",
    "season": [
        2,
        4
    ],
    "video_codec": "H.265",
    "video_profile": "High Efficiency Video Coding",
    "color_depth": "10-bit",
    "screen_size": "1080p",
    "audio_codec": "AAC",
    "release_group": "CHS&CHT",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

#### SP处理

```
For: [Neon Genesis Evangelion][Vol.09][SP04][NCED][BDRIP][1440x1080][H264_FLAC].mkv
GuessIt found: {
    "release_group": "Neon Genesis Evangelion",
    "episode": 9,
    "source": "Blu-ray",
    "other": "Rip",
    "screen_size": "1080p",
    "aspect_ratio": 1.333,
    "video_codec": "H.264",
    "audio_codec": "FLAC",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode"
}
```

需要跳过SPs, Specials, Previews, Extra, Extra/DVD Special，等多级目录。可以在获取文件列表时就过滤
```
[VCB-Studio] Sword Art Online II [Ma10p_1080p]/Previews/[VCB-Studio] Sword Art Online II [Preview10][Ma10p_1080p][x265_flac].mkv

```

OVA，可能位于一级目录
```
[VON] Tonari no Seki-Kun + ODA+OVA - [X264][FLAC][BD]/Tonari no Seki-kun - OVA 1 (DVDRip 852x480).mkv
```

#### 剧场版

混杂剧场版
```
{
    "/mnt/Disk2/BT/downloads/Video/TV_anime/[AI-Raws][Neon Genesis Evangelion_新世紀エヴァンゲリオン][TV 01-26+Movie+SP][BDRip][MKV]/[AI-Raws][アニメ BD] 新世紀エヴァンゲリオン 劇場版 Air／まごころを、君に (H264 1920x1080 FLAC[5.1ch／2ch])[05169375].mkv": {
    "source": "Blu-ray",
    "title": "新世紀エヴァンゲリオン 劇場版 Air／まごころを、君に",
    "video_codec": "H.264",
    "screen_size": "1080p",
    "aspect_ratio": 1.778,
    "audio_codec": "FLAC",
    "release_group": "[5.1ch／2ch])",
    "crc32": "05169375",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "movie",
    "season": 1,
    "episode": []
    }
},
{
    "/mnt/Disk2/BT/downloads/Video/TV_anime/[AI-Raws][Neon Genesis Evangelion_新世紀エヴァンゲリオン][TV 01-26+Movie+SP][BDRip][MKV]/[AI-Raws][アニメ BD] 新世紀エヴァンゲリオン AR／DB用定尺ラッシュビデオ 「EVANGELION：REBIRTH」 (H264 640x480 FLAC)[9F991B25].mkv": {
    "release_group": "AI-Raws",
    "source": "Blu-ray",
    "title": "新世紀エヴァンゲリオン AR／DB用定尺ラッシュビデオ 「EVANGELION：REBIRTH」",
    "video_codec": "H.264",
    "screen_size": "480p",
    "aspect_ratio": 1.333,
    "audio_codec": "FLAC",
    "crc32": "9F991B25",
    "container": "mkv",
    "mimetype": "video/x-matroska",
    "type": "episode",
    "season": 1,
    "episode": []
    }
},
```

## Thanks

- [guessit](https://github.com/guessit-io/guessit), License: LGPLv3