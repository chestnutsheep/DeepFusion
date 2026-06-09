"""Shared output schemas for tools."""

from __future__ import annotations

import csv
from io import StringIO

PRICE_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "currency",
    "source"
]

INDICATOR_COLUMNS = [
    "MACD", "DIF", "DEA",
    "KDJ.K", "KDJ.D", "KDJ.J",
    "RSI",
    "BOLL.U", "BOLL.M", "BOLL.L",
    "EMA.5", "EMA.10", "EMA.20", "EMA.60",
    "MA.5", "MA.10", "MA.20", "MA.60",
    "WILLIAMS_R",
    "CCI",
    "OBV",
    "ABV", "ABV.MA5", "ABV.MA10",
    "SAR",
    "ROC",
    "PSY",
    "BIAS.6", "BIAS.12", "BIAS.24",
    "MTM",
    "ATR14", "ADX", "DI+", "DI-",
]

RATE_COLUMNS = ["date", "rate", "currency", "source"]

ERROR_COLUMNS = ["error", "source", "fallback"]


def format_error_csv(error: str, source: str, fallback: str | None = None) -> str:
    """Return a CSV string with error contract."""

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(ERROR_COLUMNS)
    writer.writerow([error, source, fallback or ""])
    return output.getvalue().strip()
