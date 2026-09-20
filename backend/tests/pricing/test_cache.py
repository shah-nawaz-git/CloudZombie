from datetime import timedelta

from app.pricing.cache import DbPricingCache, InMemoryPricingCache


def test_in_memory_cache_expiry(fixed_clock) -> None:
    cache = InMemoryPricingCache(fixed_clock, 60)
    cache.set("key", {"value": "1"})
    assert cache.get("key") == {"value": "1"}
    fixed_clock.advance_to(fixed_clock.now() + timedelta(seconds=61))
    assert cache.get("key") is None


def test_database_cache_expiry(session_factory, fixed_clock) -> None:
    cache = DbPricingCache(session_factory, fixed_clock, 60)
    cache.set("key", {"value": "1"})
    assert cache.get("key") == {"value": "1"}
    fixed_clock.advance_to(fixed_clock.now() + timedelta(seconds=61))
    assert cache.get("key") is None
