from deep_fusion.cache import CacheKey


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
