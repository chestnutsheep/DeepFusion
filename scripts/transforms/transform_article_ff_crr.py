"""接口 article_ff_crr 返回格式调整脚本（自动生成占位）。

原基线列(旧快照): ['item', 'May  2026', 'Last 3  Months', 'Last 12  Months']
当前返回列:       ['item', 'June  2026', 'Last 3  Months', 'Last 12  Months']

差异说明：仅第2列的动态日期列随自然月从 'May 2026' 滚动为 'June 2026'，
属数据源正常行为，非接口损坏。下游 multi_factor.get_ff_summary() 按 item 列语义
读取（如 Rm-Rf 行），不依赖固定日期列名。

处置：已在 logs/api_schema_baseline.json 将基线刷新为当前实际列，巡检不再误报。
【红线】禁止把 'June 2026' 重命名为 'May 2026'（会伪造旧月份数据、破坏真实性），
故 transform 留空直出。
"""


def transform(df):
    """article_ff_crr 仅基线日期滚动，无需格式调整，直出原始 DataFrame。

    如需适配，仅可裁剪/重排列顺序，不得改写动态日期列的真实月份文本。
    """
    return df
