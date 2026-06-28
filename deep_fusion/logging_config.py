"""structlog 结构化日志配置。

日志为 JSON 格式，含 trace_id、tool、duration_ms、cache_hit 等字段，
便于后续按 trace_id 串联请求链路。
"""
from __future__ import annotations

import logging
import sys
import uuid

import structlog


def configure_logging(level: str = "WARNING") -> None:
    """配置 structlog + 标准 logging。

    在进程入口（serve.py / __init__.py:main）调用一次。
    """
    log_level = getattr(logging, level.upper(), logging.WARNING)

    # 标准库 logging 兜底
    logging.basicConfig(
        level=log_level,
        stream=sys.stdout,
        format="%(message)s",
    )

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
