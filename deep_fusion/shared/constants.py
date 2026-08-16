import os

OKX_BASE_URL = os.getenv("OKX_BASE_URL") or "https://www.okx.com"
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL") or "https://www.binance.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10) AppleWebKit/537.36 Chrome/139"
PORTFOLIO_FILE = os.path.expanduser("~/.cache/deep_fusion/portfolio.json")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

DATA_LAKE_DIR = os.path.expanduser(os.getenv("DATA_LAKE_DIR", "~/.cache/deep_fusion"))
DATA_LAKE_FILE = os.path.join(DATA_LAKE_DIR, "data_lake.db")

os.makedirs(DATA_LAKE_DIR, exist_ok=True)
