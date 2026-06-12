import pytest


@pytest.fixture(autouse=True)
def _reset_cache_registry():
    try:
        from deep_fusion import CacheKey
    except ImportError:
        yield
        return
    saved = dict(CacheKey.ALL)
    CacheKey.ALL.clear()
    yield
    CacheKey.ALL.clear()
    CacheKey.ALL.update(saved)
