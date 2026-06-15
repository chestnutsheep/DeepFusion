import pandas as pd

from deep_fusion.cache import CacheKey, ak_cache


class TestAkCacheKeyGeneration:
    """ak_cache key 生成应排除 ttl/ttl2，避免同一逻辑请求因不同 ttl 产生不同缓存条目。"""

    def test_key_excludes_ttl(self):
        """传不同 ttl 但相同业务参数，应命中同一缓存。"""
        call_count = 0
        unique_id = id(self)  # 确保每个测试方法用唯一的函数名

        def _make_fn():
            """创建一个闭包函数，带唯一 __name__ 避免跨测试冲突。"""
            def fn(x, y=1):
                nonlocal call_count
                call_count += 1
                return pd.DataFrame({"a": [x, y]})
            fn.__name__ = f"mock_fn_ttl_{unique_id}"
            return fn

        mock_fn = _make_fn()

        # 第一次调用: ttl=60
        r1 = ak_cache(mock_fn, 10, y=2, ttl=60)
        assert call_count == 1

        # 第二次调用: ttl=120 — key 应与第一次相同，命中缓存
        r2 = ak_cache(mock_fn, 10, y=2, ttl=120)
        assert call_count == 1, "ttl 不同不应产生不同缓存条目"
        pd.testing.assert_frame_equal(r1, r2)

    def test_key_excludes_ttl2(self):
        """传不同 ttl2 不应改变缓存 key。"""
        call_count = 0
        unique_id = id(self)

        def _make_fn():
            def fn(a):
                nonlocal call_count
                call_count += 1
                return pd.DataFrame({"b": [a]})
            fn.__name__ = f"mock_fn_ttl2_{unique_id}"
            return fn

        mock_fn2 = _make_fn()

        r1 = ak_cache(mock_fn2, 5, ttl=60, ttl2=120)
        assert call_count == 1

        r2 = ak_cache(mock_fn2, 5, ttl=60, ttl2=240)
        assert call_count == 1, "ttl2 不同不应产生不同缓存条目"
        pd.testing.assert_frame_equal(r1, r2)

    def test_force_bypasses_cache(self):
        """force=True 应绕过缓存，重新调用函数。"""
        call_count = 0
        unique_id = id(self)

        def _make_fn():
            def fn(x):
                nonlocal call_count
                call_count += 1
                return pd.DataFrame({"c": [x + call_count]})
            fn.__name__ = f"mock_fn_force_{unique_id}"
            return fn

        mock_fn3 = _make_fn()

        # 首次调用，填充缓存
        r1 = ak_cache(mock_fn3, 1, ttl=86400)
        assert call_count == 1

        # 不带 force，命中缓存
        r2 = ak_cache(mock_fn3, 1, ttl=86400)
        assert call_count == 1

        # 带 force，绕过缓存
        r3 = ak_cache(mock_fn3, 1, ttl=86400, force=True)
        assert call_count == 2
        # r3 应是新调用的结果（call_count=2 → x + 2 = 3）
        assert r3["c"].iloc[0] == 3


class TestCacheKey:
    def test_init_and_get_set(self):
        ck = CacheKey.init("test_init", ttl=60, ttl2=120)
        assert ck.key == "test_init"
        assert ck.ttl == 60
        assert ck.ttl2 == 120

        ck.set({"foo": "bar"})
        assert ck.get() == {"foo": "bar"}

    def test_init_dedup(self):
        ck1 = CacheKey.init("dedup_key", ttl=10)
        ck2 = CacheKey.init("dedup_key", ttl=999)
        assert ck1 is ck2

    def test_get_missing_returns_none(self):
        ck = CacheKey.init("missing_key", ttl=10)
        assert ck.get() is None

    def test_delete(self):
        ck = CacheKey.init("del_key", ttl=10)
        ck.set("data")
        assert ck.get() == "data"
        ck.delete()
        assert ck.get() is None

    def test_delete_nonexistent(self):
        ck = CacheKey.init("nonexist_del", ttl=10)
        ck.delete()

    def test_close_and_close_all(self):
        ck = CacheKey.init("close_test", ttl=10)
        ck.set("data")
        ck.close()

    def test_default_ttl2(self):
        ck = CacheKey.init("default_ttl2", ttl=300)
        assert ck.ttl2 == 600

    def test_cache_dir(self):
        ck = CacheKey.init("dir_test", ttl=10)
        p = ck.get_cache_dir()
        assert "Cache" in str(p) or ".cache" in str(p)
