#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build noonnews JSON（政策/讲话/会议驱动选股）并落库 reports.db。

设计（遵循 superdesign "设计优先"）：
  - 主源：DeepFusion 政策库（policy_cache.db）当日新增政策/讲话/会议
         → 用 CATALYST_RULES 按语义关键词命中催化 → 拆解工作环节 → 锁定环节龙头。
  - 兜底：若政策库当日为空（serve.py 每6h才跑一次，午后可能尚无当日数据），
         降级读 /tmp/noon_raw.json 的 7x24 快讯，保证不卡壳、不空跑。
  - 落库：report_writer.save_report(rtype=noonnews)，前端 DailyBoardPage 四区之一可读。

用法：
  python3 scripts/build_noonnews.py                  # 默认今天
  python3 scripts/build_noonnews.py --date 2026-08-05
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

# 兼容直接 python 运行与作为模块 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAW = "/tmp/noon_raw.json"
TODAY = datetime.now().strftime("%Y-%m-%d")
RAW_OUT_DIR = "/home/AI/scapegoat_data/午间新闻驱动选股"

# ---- 催化 → 工作环节逐级拆解 → 环节龙头（仿 obsidian 产业链拆解范式）----
# 每条规则：
#   keywords  命中政策/新闻内容即触发该催化（语义关键词，覆盖政策/讲话/会议表述）
#   direction 方向
#   links     工作环节逐级拆（原料→技术/设备→配套→应用），每个环节标"环节龙头"
#   leaders   在最细粒度环节上，按相关性最强 + 壁垒/唯一性 挑 1-2 支
# 范式来源：references/knowledge/.../钍基熔盐堆(TMSR)核心标的投资研究报告.md
CATALYST_RULES = [
    {
        "tag": "贵金属（白银/黄金突破）",
        "keywords": ["现货白银", "纽约期金", "现货黄金", "黄金", "白银", "贵金属", "避险", "储备"],
        "direction": "利好",
        "links": [
            {"环节": "原料(银矿/金矿)", "内容": "白银矿、黄金矿资源", "龙头": "兴业银锡(000426,银矿储量A股前列)/ 中金黄金(600489,黄金唯一性)", "壁垒": "资源壁垒"},
            {"环节": "冶炼提纯", "内容": "白银/黄金冶炼精炼", "龙头": "恒邦股份(002237,黄金冶炼弹性)/ 山东黄金(600547)", "壁垒": "冶炼产能"},
            {"环节": "工业应用(光伏银浆/电子)", "内容": "白银用于光伏银浆、电子触点", "龙头": "盛达资源(000603,白银纯度+储量A股最高,唯一性最强)", "壁垒": "高纯银壁垒"},
        ],
        "leaders": [
            {"code": "000603", "name": "盛达资源", "逻辑": "白银纯度/储量A股最高，银价涨直接弹性最大，环节唯一性最强", "环节": "高纯白银"},
            {"code": "600489", "name": "中金黄金", "逻辑": "黄金资源唯一性强+避险涨价双击", "环节": "黄金原料"},
        ],
    },
    {
        "tag": "工业金属（LME铜铝锌铅镍锡普涨+Codelco暂停铜矿）",
        "keywords": ["LME期铜", "LME期铝", "LME期锌", "LME期铅", "LME期镍", "LME期锡",
                     "沪铜", "沪铝", "沪锌", "沪铅", "沪镍", "沪锡", "国际铜", "铜矿", "Codelco", "有色"],
        "direction": "利好",
        "links": [
            {"环节": "原料(铜矿)", "内容": "铜精矿开采，Codelco暂停扩建加剧供给紧张", "龙头": "紫金矿业(601899,铜金矿全球前列)/ 洛阳钼业(603993,铜钴)", "壁垒": "资源壁垒"},
            {"环节": "冶炼", "内容": "铜冶炼TC/RC下行，矿端紧缺传导", "龙头": "江西铜业(600362)/ 铜陵有色(000630)", "壁垒": "冶炼产能"},
            {"环节": "加工(铜箔/铜管)", "内容": "新能源+电网用铜加工", "龙头": "海亮股份(002203,铜加工弹性)/ 博威合金(601137)", "壁垒": "加工技术"},
        ],
        "leaders": [
            {"code": "601899", "name": "紫金矿业", "逻辑": "铜金矿自给率高，铜价+Codelco停产双催化，资源壁垒最高", "环节": "铜矿原料"},
            {"code": "603993", "name": "洛阳钼业", "逻辑": "铜钴龙头，铜价弹性+刚果金矿端，与铜紧缺强相关", "环节": "铜矿原料"},
        ],
    },
    {
        "tag": "原油/能源（OPEC增产/油价）",
        "keywords": ["OPEC", "欧佩克", "霍尔木兹", "原油", "石油产量", "API", "能源", "油气", "增产"],
        "direction": "利好(油价波动+增产链)",
        "links": [
            {"环节": "开采", "内容": "上游油气开采", "龙头": "中国石油(601857)/ 中国海油(600938)", "壁垒": "资源垄断"},
            {"环节": "油服", "内容": "钻完井/增产服务", "龙头": "中海油服(601808,油服弹性最大)/ 杰瑞股份(002353)", "壁垒": "装备技术"},
            {"环节": "炼化", "内容": "炼油化工", "龙头": "中国石化(600028)", "壁垒": "炼能规模"},
        ],
        "leaders": [
            {"code": "601808", "name": "中海油服", "逻辑": "OPEC增产→海上钻完井工作量上行，油服弹性最大", "环节": "油田服务"},
            {"code": "601857", "name": "中国石油", "逻辑": "上游开采直接受益增产+油价中枢", "环节": "油气开采"},
        ],
    },
    {
        "tag": "航运/地缘（黑海遇袭/霍尔木兹）",
        "keywords": ["黑海", "航运", "霍尔木兹", "商船", "海员", "俄乌", "以色列", "伊朗", "地缘"],
        "direction": "利好(运价上行+避险)",
        "links": [
            {"环节": "运力(集运)", "内容": "集装箱运力，绕航+地缘推升运价", "龙头": "中远海控(601919,集运龙头)/ 海丰国际", "壁垒": "船队规模"},
            {"环节": "油运", "内容": "原油/成品油运输", "龙头": "招商轮船(601872,油运弹性)/ 中远海能(600026)", "壁垒": "油轮船队"},
            {"环节": "造船/港口", "内容": "新船订单+港口吞吐", "龙头": "中国船舶(600150)", "壁垒": "造船产能"},
        ],
        "leaders": [
            {"code": "601919", "name": "中远海控", "逻辑": "集运龙头，绕航+地缘推升运价，弹性最高", "环节": "集装箱运力"},
            {"code": "601872", "name": "招商轮船", "逻辑": "油运弹性，霍尔木兹风险溢价直接受益", "环节": "原油运输"},
        ],
    },
    {
        "tag": "消费电子/苹果链（发布会/以旧换新）",
        "keywords": ["苹果", "iPhone", "发布会", "Ternus", "库克", "消费电子", "以旧换新", "手机"],
        "direction": "利好",
        "links": [
            {"环节": "代工/组装", "内容": "iPhone整机组装", "龙头": "立讯精密(002475,组装龙头)/ 工业富联(601138)", "壁垒": "精密制造"},
            {"环节": "结构件/玻璃盖板", "内容": "金属中框+玻璃盖板", "龙头": "蓝思科技(300433,玻璃盖板)/ 领益智造(002600)", "壁垒": "工艺壁垒"},
            {"环节": "光学/检测", "内容": "摄像头模组+设备检测", "龙头": "歌尔股份(002241)/ 赛腾股份(603283)", "壁垒": "光学技术"},
        ],
        "leaders": [
            {"code": "002475", "name": "立讯精密", "逻辑": "iPhone组装份额提升+新品备货，相关性最强", "环节": "整机组装"},
            {"code": "300433", "name": "蓝思科技", "逻辑": "玻璃盖板核心供应，单机价值量高", "环节": "玻璃盖板"},
        ],
    },
    {
        "tag": "美股风险偏好（纳指/标普新高）",
        "keywords": ["纳斯达克", "标普", "道指", "美股", "盘中新高", "风险偏好", "科技股"],
        "direction": "利好(风险偏好外溢)",
        "links": [
            {"环节": "半导体(科创板)", "内容": "科技成长情绪外溢", "龙头": "中芯国际(688981,半导体设备情绪锚)", "壁垒": "国产替代"},
            {"环节": "新能源(创业板)", "内容": "高贝塔成长", "龙头": "宁德时代(300750,创业板权重)", "壁垒": "电池龙头"},
        ],
        "leaders": [
            {"code": "688981", "name": "中芯国际", "逻辑": "纳指新高→科技风险偏好外溢，半导体情绪锚", "环节": "半导体"},
            {"code": "300750", "name": "宁德时代", "逻辑": "创业板权重+高贝塔，风险偏好修复直接受益", "环节": "新能源"},
        ],
    },
]


def match_rule(content):
    hits = []
    for rule in CATALYST_RULES:
        if any(k in content for k in rule["keywords"]):
            hits.append(rule)
    return hits


def load_policy_items(date):
    """从政策库读取当日政策/讲话/会议（主源）。

    Returns: list[{time, content, src, url}]；库不可用时返回空列表。
    """
    try:
        from deep_fusion.shared.policy_db import PolicyDB
        db = PolicyDB()
        rows = db.search(limit=200)
        out = []
        for r in rows:
            pd = (r.get("publish_date") or "")[:10]
            if pd != date:
                continue
            title = r.get("title") or ""
            body = r.get("body") or ""
            org = r.get("organization") or r.get("source") or ""
            content = f"[{org}] {title}。{body}".strip()
            out.append({"time": pd, "content": content, "src": org, "url": r.get("url", "")})
        return out
    except Exception as e:
        print("[warn] 政策库读取失败，走兜底:", e)
        return []


def load_raw_items(date):
    """兜底：读 /tmp/noon_raw.json 的 7x24 快讯（当日）。"""
    if not os.path.exists(RAW):
        return []
    try:
        items = json.load(open(RAW, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for x in items:
        t = x.get("time", "")
        if not t.startswith(date):
            continue
        out.append({"time": t, "content": x.get("content", ""),
                    "src": x.get("src", "新浪财经"), "url": ""})
    out.sort(key=lambda x: x["time"], reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=TODAY, help="数据日期 YYYY-MM-DD（默认今天）")
    args = ap.parse_args()
    DATE = args.date

    # 主源：政策库当日政策；兜底：7x24 快讯
    items = load_policy_items(DATE)
    source_label = "政策库(政策/讲话/会议)"
    if not items:
        print("[info] 政策库当日为空，降级 7x24 快讯兜底")
        items = load_raw_items(DATE)
        source_label = "新浪财经7x24全球快讯(兜底)"

    catalysts = []
    timeline = []
    seen_tags = set()

    for x in items:
        content = x.get("content", "")
        t = x.get("time", "")
        src = x.get("src", "")
        url = x.get("url", "")
        hits = match_rule(content)
        if not hits:
            timeline.append({"time": t, "content": content[:240], "src": src,
                             "url": url, "tag": "", "direction": "", "leaders": [], "links": []})
            continue
        for rule in hits:
            timeline.append({
                "time": t, "content": content[:240], "src": src, "url": url,
                "tag": rule["tag"], "direction": rule["direction"],
                "leaders": rule.get("leaders", []), "links": rule.get("links", []),
            })
            if rule["tag"] in seen_tags:
                continue
            seen_tags.add(rule["tag"])
            catalysts.append({
                "tag": rule["tag"],
                "direction": rule["direction"],
                "links": rule.get("links", []),
                "leaders": rule.get("leaders", []),
                "evidence": content[:160],
                "time": t,
            })

    payload = {
        "date": DATE,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": (f"午间新闻驱动选股（政策/讲话/会议驱动 + 产业链环节拆解）：从 {len(items)} 条"
                    f"{source_label}中识别 {len(catalysts)} 条催化，每条拆解工作环节并锁定 1-2 支环节龙头。"),
        "catalyst_count": len(catalysts),
        "catalysts": catalysts,
        "timeline": timeline,
        "data_source": source_label,
        "method": "政策/讲话/会议→语义关键词命中催化→工作环节逐级拆(原料/技术/设备/配套/应用)→最小粒度环节挑相关性最强+壁垒最高1-2支(仿obsidian钍基熔盐堆拆解范式)",
        "note": "数据时效优先；政策经 serve.py 每6h采集，午后可能尚无当日条目时会自动降级7x24快讯。环节龙头为逻辑相关性判断，非投资建议。",
    }

    # 保存原始 JSON 供渲染
    os.makedirs(RAW_OUT_DIR, exist_ok=True)
    out_json = os.path.join(RAW_OUT_DIR, f"{DATE}.raw.json")
    json.dump(payload, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("WROTE", out_json)

    # 落库 reports.db
    cmd = [
        sys.executable, "scripts/report_writer.py",
        "--action", "save_report",
        "--rtype", "noonnews",
        "--date", DATE,
        "--json", json.dumps(payload, ensure_ascii=False),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("DB_OUT", res.stdout.strip()[-300:])
    if res.returncode != 0:
        print("DB_ERR", res.stderr.strip()[-500:])


if __name__ == "__main__":
    main()
