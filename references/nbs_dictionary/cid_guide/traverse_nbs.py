"""NBS CID 全面遍历脚本 — v2: 仅遍历叶子节点 + 断点续传

遍历国家统计局 V2.0 API 所有月/季数据集，收集：
- CID 元数据（名称、时间范围、是否时间分片）
- 指标列表（名称、单位、小数位、口径说明）
- 按领域自动分类

输出：
- assets/id_reflection/cid_guide/cid_metadata.json      # 完整元数据
- assets/id_reflection/cid_guide/monthly/{domain}.md    # 月度按领域分档
- assets/id_reflection/cid_guide/quarterly/{domain}.md  # 季度按领域分档
- assets/id_reflection/cid_guide/index.md               # 总索引
- 同格式 Obsidian 备份
"""

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

CYCLES_DIR = Path("/home/AI/workspace/cycles")
sys.path.insert(0, str(CYCLES_DIR / "scripts"))
from nbs_client import NbsClient

OUTPUT_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = OUTPUT_DIR / ".checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# 领域分类关键词（按 NBS 实际命名习惯）
DOMAIN_RULES = [
    ("居民消费价格", ["居民消费价格", "商品零售价格", "CPI"]),
    ("工业生产者价格", ["工业生产者出厂价格", "工业生产者购进价格", "PPI"]),
    ("工业生产", ["规上工业", "工业增加值", "工业主要经济指标", "工业企业", "工业产销"]),
    ("固定资产投资", ["固定资产投资", "房地产投资", "建筑业"]),
    ("能源", ["能源", "煤炭", "石油", "天然气", "电力", "热力", "燃气"]),
    ("交通运输", ["交通", "运输", "邮电", "铁路", "公路", "民航", "港口"]),
    ("国内贸易", ["社会消费品", "批发", "零售", "住宿", "餐饮", "消费品市场"]),
    ("对外贸易", ["进出口", "出口", "进口", "贸易"]),
    ("财政金融", ["财政", "金融", "货币", "信贷", "税收", "LPR"]),
    ("就业工资", ["就业", "失业", "工资", "劳动报酬"]),
    ("人口民生", ["人口", "人民生活", "教育", "卫生", "社保"]),
    ("农业", ["农业", "农林牧渔", "农产品", "粮食", "种植"]),
    ("景气调查", ["景气", "PMI", "采购经理", "企业调查", "信心"]),
    ("科学技术", ["科技", "研发", "专利", "创新"]),
    ("环境资源", ["环境", "资源", "生态", "碳排放"]),
    ("区域经济", ["区域", "地区", "分省", "城市", "东中"],
     ),
]


# ── 辅助函数 ──────────────────────────────────

def classify_domain(name: str) -> str:
    for domain, kws in DOMAIN_RULES:
        if any(kw in name for kw in kws):
            return domain
    return "其他/综合"


def is_time_split(name: str) -> bool:
    """判断是否为时间分片 CID（如"全国CPI (2021-2025)""）"""
    return bool(re.search(r'\(\d{4}-\)|\(\d{4}-\d{4}\)|\(-\d{4}\)', name))


def strip_time_suffix(name: str) -> str:
    return re.sub(r'\s*\(\d{4}-\)\s*|\s*\(\d{4}-\d{4}\)\s*|\s*\(-\d{4}\)\s*', '', name).strip()


def inspect_cid(client: NbsClient, cid_entry: dict, freq_key: str) -> dict:
    """检查单个 CID，返回结构化元数据"""
    cid = cid_entry["id"]
    name = cid_entry.get("name", "无名称")
    sdate = cid_entry.get("sdate")
    edate = cid_entry.get("edate")

    entry = {
        "cid": cid,
        "name": name,
        "base_name": strip_time_suffix(name),
        "freq": freq_key,
        "sdate": sdate,
        "edate": edate,
        "is_time_split": is_time_split(name),
        "domain": classify_domain(name),
        "indicators": [],
        "_error": None,
    }

    try:
        indicators = client.get_indicators(cid, use_cache=False)
        for ind in indicators:
            entry["indicators"].append({
                "id": ind.get("_id", ""),
                "name": ind.get("i_showname", ""),
                "unit": ind.get("du", ""),
                "decimals": ind.get("dp", 0),
                "mark": ind.get("i_mark", "")[:200],
            })
    except Exception as e:
        entry["_error"] = str(e)[:100]

    return entry


def traverse_freq(client: NbsClient, freq_key: str, resume: bool = True) -> list[dict]:
    """遍历单一频率的所有叶子 CID"""
    cid_list = json.loads(
        (CYCLES_DIR / "data" / f"nbs_cids_{freq_key}.json").read_text(encoding="utf-8")
    )
    checkpoint_path = CHECKPOINT_DIR / f"{freq_key}.json"
    total = len(cid_list)

    print(f"[{freq_key}] 共 {total} 条 CID 索引")

    # 筛选叶子节点
    leaf_cids = [c for c in cid_list if c.get("isLeaf", False)]
    print(f"    → 叶子节点: {len(leaf_cids)}")

    # 加载断点
    results = []
    done_ids = set()
    if resume and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        results = saved
        done_ids = {r["cid"] for r in results}
        print(f"    → 已有 {len(done_ids)} 个, 续遍历 {len(leaf_cids) - len(done_ids)} 个")

    # 遍历
    start_time = time.time()
    for i, entry in enumerate(leaf_cids):
        cid = entry["id"]
        if cid in done_ids:
            continue

        result = inspect_cid(client, entry, freq_key)
        results.append(result)
        done_ids.add(cid)

        if (i + 1) % 20 == 0:
            checkpoint_path.write_text(
                json.dumps(results, ensure_ascii=False, default=str), encoding="utf-8",
            )
            elapsed = time.time() - start_time
            rate = len(done_ids) / max(elapsed, 0.1)
            rem = (len(leaf_cids) - len(done_ids)) / max(rate, 0.1)
            print(f"    [{freq_key}] {len(done_ids)}/{len(leaf_cids)}  "
                  f"({rate:.1f}/s, 预计剩余 {rem:.0f}s)   ", end="\r")

    checkpoint_path.write_text(
        json.dumps(results, ensure_ascii=False, default=str), encoding="utf-8",
    )
    elapsed = time.time() - start_time
    print(
        f"\n    ✅ [{freq_key}] {len(results)} 个 CID, {sum(len(r['indicators']) for r in results)} 个指标, 耗时 {elapsed:.0f}s")
    return results


# ── Markdown 生成 ─────────────────────────────

def escape_md(text):
    if not text: return "—"
    return text.replace("|", "\\|")


def generate_docs(metadata: dict, freq_key: str, output_dir: Path):
    """按领域生成 markdown 页面"""
    entries = metadata[freq_key]
    freq_label = {"monthly": "月度", "quarterly": "季度", "annual": "年度"}.get(freq_key, freq_key)
    freq_dir = output_dir / freq_key
    freq_dir.mkdir(parents=True, exist_ok=True)

    # 按领域分组
    groups = {}
    for e in entries:
        d = e.get("domain", "其他/综合")
        groups.setdefault(d, []).append(e)

    # 领域索引页
    index_lines = [
        f"---",
        f"title: NBS {freq_label}数据 — CID 索引",
        f"tags: [nbs, cid-guide, {freq_key}]",
        f"---",
        f"",
        f"# NBS {freq_label}数据全景",
        f"",
        f"| 维度 | 数值 |",
        f"|---|---|",
        f"| 数据集(CID)数 | {len(entries)} |",
        f"| 指标总数 | {sum(len(e['indicators']) for e in entries)} |",
        f"| 领域覆盖 | {len(groups)} 个 |",
        f"| 异常请求 | {sum(1 for e in entries if e.get('_error'))} |",
        f"| 时间分片数 | {sum(1 for e in entries if e.get('is_time_split'))} |",
        f"",
    ]

    for domain in sorted(groups.keys()):
        g = groups[domain]
        ind_total = sum(len(e["indicators"]) for e in g)
        slug = domain.replace("/", "_").replace(" ", "_")
        page_file = freq_dir / f"{slug}.md"

        # 领域页
        page_lines = [
            f"---",
            f"title: {domain} — {freq_label}",
            f"tags: [nbs, {freq_key}, {slug}]",
            f"---",
            f"",
            f"# {domain} — NBS {freq_label}数据",
            f"",
            f"> 共 **{len(g)}** 个数据集, **{ind_total}** 个指标",
            f"",
        ]

        # 汇总：按时间分片分组
        base_groups = {}
        for e in g:
            base = e["base_name"]
            base_groups.setdefault(base, []).append(e)

        for base_name in sorted(base_groups.keys()):
            cid_group = base_groups[base_name]
            if len(cid_group) == 1:
                e = cid_group[0]
                # 单 CID
                page_lines.append(f"### {e['name']}")
                page_lines.append(f"")
                page_lines.append(
                    f"**CID:** `{e['cid'][:16]}...`  |  **时间范围:** {e.get('sdate') or '?'} → {e.get('edate') or '至今'}")
            else:
                # 多时间分片
                page_lines.append(f"### {base_name}（{len(cid_group)} 个分片）")
                page_lines.append(f"")
                page_lines.append(f"| 分片 | CID | 时间范围 |")
                page_lines.append(f"|---|---|---|")
                for e in sorted(cid_group, key=lambda x: x.get("sdate") or "0"):
                    dr = f"{e.get('sdate') or '?'} → {e.get('edate') or '?'}"
                    page_lines.append(f"| {e['name']} | `{e['cid'][:16]}...` | {dr} |")
                page_lines.append(f"")

            if e.get("_error"):
                page_lines.append(f"> [!warning] 该 CID 请求异常: {e['_error']}")
                page_lines.append(f"")
                continue

            inds = e.get("indicators", [])
            if not inds:
                page_lines.append(f"> [!note] 无指标数据（可能是导航节点）")
                page_lines.append(f"")
                continue

            # 指标表格
            page_lines.append(f"**指标（{len(inds)} 个）:**")
            page_lines.append(f"")
            page_lines.append(f"| 指标名称 | 单位 | 口径说明 |")
            page_lines.append(f"|---|---|---|")
            for ind in inds[:15]:  # 前15个
                page_lines.append(
                    f"| {escape_md(ind['name'])} "
                    f"| {escape_md(ind.get('unit', ''))} "
                    f"| {escape_md(ind.get('mark', ''))[:60]} |"
                )
            if len(inds) > 15:
                page_lines.append(f"| *... 还有 {len(inds) - 15} 个指标* | | |")
            page_lines.append(f"")
            page_lines.append(f"---")
            page_lines.append(f"")

        page_file.write_text("\n".join(page_lines), encoding="utf-8")
        print(f"    → {freq_key}/{slug}.md")

        # 主索引条目
        index_lines.append(f"## [[{slug}|{domain}]]")
        index_lines.append(f"")
        index_lines.append(f"- 数据集: {len(g)} 个, 指标: {ind_total} 个")
        index_lines.append(f"- 时间分片组: {len(base_groups)} 个")
        index_lines.append(f"")

    # 写入索引
    (freq_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")
    print(f"    ✅ {freq_key}/index.md")


def generate_main_index(metadata: dict, output_dir: Path):
    lines = [
        f"---",
        f"title: NBS 数据全景 CID Guide",
        f"tags: [nbs, cid-guide, 数据目录]",
        f"---",
        f"",
        f"# NBS 数据全景 CID Guide",
        f"",
        f"> 国家统计局 V2.0 API | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 完整数据集遍历清单",
        f"> 数据源: https://data.stats.gov.cn",
        f"",
        f"## 频率索引",
        f"",
        f"| 频率 | 数据集数 | 指标总数 | 领域覆盖 |",
        f"|---|---|---|---|",
    ]
    for freq_key, label in [("monthly", "月度"), ("quarterly", "季度"), ("annual", "年度")]:
        m = metadata.get(freq_key, [])
        domains = len(set(e.get("domain", "其他") for e in m))
        inds = sum(len(e.get("indicators", [])) for e in m)
        lines.append(f"| [[{freq_key}/index|{label}]] | {len(m)} | {inds} | {domains} |")

    lines.extend([
        f"",
        f"## 全域总览",
        f"",
    ])
    all_entries = []
    for freq_key in ["monthly", "quarterly", "annual"]:
        all_entries.extend(metadata.get(freq_key, []))
    all_domains = {}
    for e in all_entries:
        d = e.get("domain", "其他/综合")
        all_domains.setdefault(d, []).append(e)

    lines.extend([
        f"| 领域 | 数据集(CID) | 指标总数 | 涉及频率 |",
        f"|---|---|---|---|",
    ])
    for d in sorted(all_domains.keys()):
        g = all_domains[d]
        total_inds = sum(len(e["indicators"]) for e in g)
        freqs = set(e["freq"] for e in g)
        freq_label = "月" if "monthly" in freqs else ""
        freq_label += "季" if "quarterly" in freqs else ""
        freq_label += "年" if "annual" in freqs else ""
        lines.append(f"| {d} | {len(g)} | {total_inds} | {freq_label} |")

    lines.extend([
        f"",
        f"## 机器可读元数据",
        f"",
        f"完整元数据文件: `cid_metadata.json`（同目录下）",
        f"",
        f"## 遍历脚本",
        f"",
        f"```bash",
        f"python3 traverse_nbs.py  # 按月/季/年全量遍历",
        f"```",
        f"",
        f"## 说明",
        f"",
        f"- 时间分片: 同一指标可能跨多个CID（如CPI有4个时间分片）",
        f"- 口径说明(i_mark): 每个指标附带统计口径,是理解数据含义的关键",
        f"- 部分CID是导航节点(无指标数据)",
        f"",
    ])
    (output_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"    ✅ index.md")


# ── 主入口 ──────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--freq", choices=["monthly", "quarterly", "annual", "all"],
                        default="all")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--obsidian", type=str, default=None,
                        help="Obsidian vault 路径, 用于备份")
    args = parser.parse_args()

    if args.no_resume and CHECKPOINT_DIR.exists():
        shutil.rmtree(CHECKPOINT_DIR)
        CHECKPOINT_DIR.mkdir()

    freqs = ["monthly", "quarterly", "annual"] if args.freq == "all" else [args.freq]
    client = NbsClient()
    metadata = {}

    for freq in freqs:
        print(f"\n{'=' * 60}")
        print(f"  遍历 {freq} 数据")
        print(f"{'=' * 60}")
        metadata[freq] = traverse_freq(client, freq, resume=not args.no_resume)

    # 保存 JSON 元数据
    meta_path = OUTPUT_DIR / "cid_metadata.json"
    meta_path.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "stats": {f: {
                "total": len(metadata[f]),
                "indicators": sum(len(e["indicators"]) for e in metadata[f]),
                "domains": len(set(e.get("domain") for e in metadata[f])),
                "time_splits": sum(1 for e in metadata[f] if e.get("is_time_split")),
                "errors": sum(1 for e in metadata[f] if e.get("_error")),
            } for f in metadata},
            "cids": metadata,
        }, ensure_ascii=False, default=str, indent=2),
        encoding="utf-8",
    )
    print(f"\n[*] 元数据保存: {meta_path}")

    # 生成文档
    print(f"\n{'=' * 60}")
    print(f"  生成文档")
    print(f"{'=' * 60}")
    for freq in freqs:
        generate_docs(metadata, freq, OUTPUT_DIR)
    generate_main_index(metadata, OUTPUT_DIR)

    # Obsidian 备份
    if args.obsidian:
        vault_dir = Path(args.obsidian)
        obsidian_target = vault_dir / "NBS数据目录"
        obsidian_target.mkdir(parents=True, exist_ok=True)
        for freq in freqs:
            src_dir = OUTPUT_DIR / freq
            if src_dir.exists():
                shutil.copytree(src_dir, obsidian_target / freq, dirs_exist_ok=True)
        src = OUTPUT_DIR / "index.md"
        if src.exists():
            shutil.copy2(src, obsidian_target / "index.md")
        print(f"    → Obsidian 备份: {obsidian_target}")

    print(f"\n{'=' * 60}")
    print(f"  全部完成!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
