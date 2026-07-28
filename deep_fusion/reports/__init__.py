"""结构化报告存储层。

把四个定时任务(premarket/noonnews/qualitystock/dailyreview)的 JSON、
连板潜力股识别结果、金融大事日历事件统一落到 SQLite(reports.db)，
供 DeepFusion 前端实时查询 + 历史回溯。

数据库路径优先级：显式 db_path 参数 > 环境变量 REPORTS_DB_PATH > 默认 <repo>/data/reports.db
（默认路径已被 .gitignore 的 `data/*.db` 忽略，不会上传，符合"省内存/历史留档"目标）。
"""
