# 热点 / 舆情补充源（Node 脚本）

来源：hot skill（热点数据采集），原样拷贝至本地，避免每次翻 skill 文件。

这些脚本输出 JSON 到 stdout，可作为"行情之外的市场情绪 / 舆情热度"补充源，
与 Python 政策/监管渠道（上级目录）互补。

## 用法

```bash
# 热搜（抖音/微博/百度/B站/快手）
node crawl-hot.js                      # 全部平台
node crawl-hot.js --platform=weibo    # 单平台

# 音乐热榜（QQ/网易云/酷狗/酷我）
node crawl-music.js
node crawl-music.js --platform=netease

# 影视/游戏（猫眼票房 / App Store 排行）
node crawl-entertainment.js --type=all
node crawl-entertainment.js --type=movie

# 人民日报电子版
node crawl-paper.js
node crawl-paper.js --date=yesterday
```

## 调用入口

Python 侧可通过 `deep_fusion.data.sources.scrapers.run_hot(platform)` 直接调用
`crawl-hot.js`，返回脚本 stdout 的 JSON。
