"""热点/投资方向（invest_theme）MCP 工具。

功能：
- invest_theme_collect : 手动保底入口。传入关键词(或已整理的主题数据) → 整理标准化 →
                         写入 reports.db (rtype='invest_theme')，与每日报告区其他报告一并管理。
- invest_theme_latest  : 取最新一期热点/投资方向标的组合（含次日涨跌强度回测）。
- invest_theme_history : 历史列表（按日期切换查看）。
- invest_theme_date    : 按指定日期取某日标的组合。

典型用法（自动/手动）：
1) 自动化定时任务蹲政策站点/专利库 → agent 流程采集整理 → 调用 invest_theme_collect 落库。
2) 用户在看板「主题输入框」输入关键词 → 触发 invest_theme_collect，agent 收到关键词后
   上网/专利库搜集 → 整理为 themes 列表 → 回传本工具入库。
"""
import json
from datetime import date, datetime

from ..server import mcp
from ..reports.store import (
    save_invest_theme, get_invest_theme_latest,
    get_invest_theme_history, get_invest_theme,
)


def _norm_target(t):
    """标准化单只标的记录，兼容写死数据与实时回测字段。"""
    return {
        "code": str(t.get("code", "")),
        "name": str(t.get("name", "")),
        "pct": t.get("pct", t.get("change", "")),      # 当日涨跌
        "change": t.get("change", ""),
        "reason": t.get("reason", ""),
        "intensity": t.get("intensity", ""),           # 强度：强/中/弱
        "next_day": t.get("next_day") or {},           # 次日涨跌与强度回测
    }


def _norm_theme(th):
    """标准化单条主题记录。"""
    return {
        "theme": str(th.get("theme", th.get("name", ""))),
        "summary": str(th.get("summary", "")),
        "sentiment": th.get("sentiment", "中性"),
        "targets": [_norm_target(x) for x in (th.get("targets") or [])],
        "sources": th.get("sources") or [],
    }


@mcp.tool(
    name="invest_theme_collect",
    description="热点/投资方向采集落库：传入关键词或已整理的主题数据，标准化后写入 reports.db "
                "(rtype='invest_theme')，与每日报告区其他报告一并管理维护。可作为自动化定时任务的落库入口，"
                "也可作为看板「主题输入框」手动触发后 agent 整理数据的回写入库点。",
)
def invest_theme_collect(
    keywords: str = "",
    themes: str = "",
    rpt_date: str = "",
):
    """采集/整理热点投资方向并落库。

    Args:
        keywords: 逗号分隔的关键词（如 "AI算力,低空经济,半导体"）。用于生成主题骨架；
                  若同时传入 themes（已整理数据），以 themes 为准合并。
        themes:   已整理的主题 JSON 字符串（list[dict]）。每条字段：
                   theme(主题名), summary(拆解), sentiment(利好/利空/中性),
                   targets(list[{code,name,pct,reason,intensity,next_day}]), sources(list)。
        rpt_date: 报告日期(YYYY-MM-DD)，默认今天。

    Returns:
        text 报告：落库条数、日期、主题清单。
    """
    rpt_date = rpt_date or date.today().isoformat()
    parsed_themes = []

    # 1) 结构化数据优先
    if themes:
        try:
            raw = json.loads(themes) if isinstance(themes, str) else themes
            if isinstance(raw, dict):
                raw = [raw]
            if isinstance(raw, list):
                parsed_themes.extend(_norm_theme(x) for x in raw)
        except json.JSONDecodeError as e:
            return f"[错误] themes JSON 解析失败: {e}\n请传入合法 JSON 列表。"

    # 2) 仅有关键词：生成空主题骨架，待 agent 流程联网/专利库填充
    if keywords and not parsed_themes:
        for kw in [k.strip() for k in keywords.split(",") if k.strip()]:
            parsed_themes.append(_norm_theme({
                "theme": kw, "summary": "", "sentiment": "中性", "targets": [],
                "sources": ["关键词触发-待采集"],
            }))

    if not parsed_themes:
        return ("[提示] 未传入任何关键词或主题数据。\n"
                "用法示例：\n"
                "  invest_theme_collect(keywords='AI算力,低空经济')\n"
                "  invest_theme_collect(themes='[{\"theme\":\"AI算力\",\"targets\":[{\"code\":\"300750\",\"name\":\"宁德时代\"}]}]')")

    # 1.5) 补全 targets：对空 targets 的主题，按"已实测验证的主题→个股映射"补关联标的；
    #      遵循题材猎手方法论——不联网硬凑，无匹配则留空。
    from ..data.sources.scrapers.theme_enrich import enrich_themes
    enrich_themes(parsed_themes)

    save_invest_theme(parsed_themes, rpt_date=rpt_date)
    lines = [f"✅ 热点/投资方向已落库  ({rpt_date})  共 {len(parsed_themes)} 个主题："]
    for i, t in enumerate(parsed_themes, 1):
        n_tgt = len(t["targets"])
        lines.append(f"  {i}. {t['theme']}  [{t['sentiment']}]  标的 {n_tgt} 只")
    lines.append("")
    lines.append("说明：自动化定时任务 / 看板关键词触发后，agent 将联网与专利库搜集的信息按此结构回写即可。")
    return "\n".join(lines)


@mcp.tool(
    name="invest_theme_latest",
    description="取最新一期热点/投资方向标的组合（含次日涨跌强度回测）。",
)
def invest_theme_latest():
    """最新一期热点/投资方向。"""
    row = get_invest_theme_latest()
    if not row:
        return "暂无热点/投资方向数据。可用 invest_theme_collect 落库。"
    payload = row["payload"] if isinstance(row, dict) else json.loads(row[2])
    if isinstance(payload, dict):
        payload.setdefault("created_at", row.get("created_at") if isinstance(row, dict) else None)
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool(
    name="invest_theme_history",
    description="热点/投资方向历史列表（按日期降序，用于看板切换日期）。",
)
def invest_theme_history(limit: int = 30):
    """历史列表。"""
    rows = get_invest_theme_history(limit=limit)
    if not rows:
        return "[]"
    out = [{"date": r["date"], "n_themes": len((r["payload"] or {}).get("themes", []))}
           for r in rows]
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool(
    name="invest_theme_date",
    description="按指定日期取某日热点/投资方向标的组合（看板日期切换查看）。",
)
def invest_theme_date(rpt_date: str):
    """按日期取。"""
    row = get_invest_theme(rpt_date)
    if not row:
        return json.dumps({"date": rpt_date, "created_at": None, "themes": []}, ensure_ascii=False)
    payload = row["payload"] if isinstance(row, dict) else json.loads(row[2])
    if isinstance(payload, dict):
        payload.setdefault("created_at", row.get("created_at") if isinstance(row, dict) else None)
    return json.dumps(payload, ensure_ascii=False, indent=2)
