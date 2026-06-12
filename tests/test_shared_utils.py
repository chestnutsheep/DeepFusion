import os
import tempfile

import pytest

from deep_fusion.cache import CacheKey


class TestAkCache:
    def test_cache_key_generation(self):
        def dummy_func(a, b=None):
            return f"{a}-{b}"

        ck = CacheKey.init("dummy_func-('hello',)-{'b': 'world'}", ttl=60)
        ck.set("cached_result")
        assert ck.get() == "cached_result"

    def test_cache_l1_faster_than_l2(self):
        ck = CacheKey.init("l1_l2_test", ttl=3600)
        ck.set("value")
        assert ck.get() == "value"
        ck.cache1.pop(ck.key, None)
        assert ck.get() == "value"


class TestPortfolioIO:
    def test_load_portfolio_non_existent(self):
        from deep_fusion.shared.utils import load_portfolio
        result = load_portfolio()
        assert isinstance(result, dict)

    @pytest.fixture
    def temp_portfolio(self, monkeypatch):
        tmpdir = tempfile.mkdtemp()
        tmpfile = os.path.join(tmpdir, "portfolio.json")
        monkeypatch.setattr("deep_fusion.shared.constants.PORTFOLIO_FILE", tmpfile)
        return tmpfile

    def test_save_and_load(self, temp_portfolio):
        from deep_fusion.shared.utils import save_portfolio, load_portfolio
        data = {"000001": {"symbol": "000001", "price": 10.0, "volume": 100}}
        save_portfolio(data)
        loaded = load_portfolio()
        assert loaded == data
