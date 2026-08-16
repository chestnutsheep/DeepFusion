"""structlog 结构化日志配置。

日志为 JSON 格式，含 trace_id、tool、duration_ms、cache_hit 等字段，
便于后续按 trace_id 串联请求链路。
"""
from __future__ import annotations

import logging
import sys
import uuid
import warnings
from pathlib import Path

try:
    import structlog
except ImportError:
    # 降级：环境缺 structlog 时（如误用原生 python3 启动），用标准 logging 模拟，
    # 避免整个进程 import 阶段崩溃 → serve.py 后台线程(定时任务)全部不工作。
    import logging as _std_logging

    class _StructlogFallback:
        def get_logger(self, name: str | None = None):
            return _std_logging.getLogger(name or __name__)

        def configure(self, *args, **kwargs):
            pass

        def wrap_logger(self, *args, **kwargs):
            return self.get_logger()

    structlog = _StructlogFallback()  # type: ignore

# 集中落盘位置：所有运行时 info/warn/error（含 akshare 超时、政策采集、
# 非交易日告警等）统一写入此文件，JSON 行，前端调试抽屉读取尾部。
LOG_DIR = Path.home() / "output" / "data" / "logs"
RUNTIME_LOG = LOG_DIR / "runtime.log"


def configure_logging(level: str = "WARNING") -> None:
    """配置 structlog + 标准 logging，同时落盘 runtime.log。

    在进程入口（serve.py / __init__.py:main）调用一次。
    """
    log_level = getattr(logging, level.upper(), logging.WARNING)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 标准库 logging 兜底：stderr + 文件（JSON 行，UTF-8）。
    # 注意：本进程既是 MCP stdio 服务（stdout 是 JSON-RPC 协议通道），
    # 也常作为 CLI 使用。日志打到 stdout 会污染 stdio 协议流导致客户端
    # JSON 解析失败，因此只能走 stderr（CLI 模式 stderr 同样安全可见）。
    _file_handler = logging.FileHandler(str(RUNTIME_LOG), encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.basicConfig(
        level=log_level,
        handlers=[logging.StreamHandler(sys.stderr), _file_handler],
        format="%(message)s",
    )

    # 接管 akshare 的 UserWarning（如「20210206非交易日」）到 logger，
    # 避免散落 stderr 且带 traceback 噪声。
    warnings.simplefilter("default")
    # 抑制 websockets 14+/uvicorn 0.46 的 legacy 弃用警告（不影响功能，仅启动噪声）
    warnings.filterwarnings(
        "ignore",
        message=r"websockets\.legacy is deprecated",
        category=DeprecationWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"websockets\.server\.WebSocketServerProtocol is deprecated",
        category=DeprecationWarning,
    )
    logging.getLogger("py.warnings").addHandler(logging.NullHandler())
    _orig_showwarning = warnings.showwarning

    def _akshare_warning_to_log(message, category, filename, lineno, file=None, line=None):
        msg = str(message)
        if "非交易日" in msg or "akshare" in filename:
            get_logger("akshare").warning("akshare_warning", warning=msg, file=filename, lineno=lineno)
        else:
            _orig_showwarning(message, category, filename, lineno, file, line)

    warnings.showwarning = _akshare_warning_to_log

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _inject_trace_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        cache_logger_on_first_use=True,
    )


def _inject_trace_id(_logger: object, _method_name: str, event_dict: dict) -> dict:
    """注入 trace_id（若上下文未设置则生成新的）。"""
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = uuid.uuid4().hex[:16]
    return event_dict


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取 structlog logger。"""
    return structlog.get_logger(name)
