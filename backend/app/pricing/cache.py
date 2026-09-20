from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.persistence.models import PricingCache as PricingCacheRecord


class PricingCache(Protocol):
    def get(self, key: str) -> dict | None: ...

    def set(self, key: str, payload: dict) -> None: ...


class InMemoryPricingCache:
    def __init__(self, clock: Clock, ttl_seconds: int) -> None:
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[datetime, dict]] = {}

    def get(self, key: str) -> dict | None:
        item = self._items.get(key)
        if item is None:
            return None
        fetched_at, payload = item
        if (self._clock.now() - fetched_at).total_seconds() > self._ttl_seconds:
            return None
        return deepcopy(payload)

    def set(self, key: str, payload: dict) -> None:
        self._items[key] = (self._clock.now(), deepcopy(payload))


class DbPricingCache:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Clock,
        ttl_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> dict | None:
        with self._session_factory() as session:
            record = session.get(PricingCacheRecord, key)
            if record is None:
                return None
            if (self._clock.now() - record.fetched_at).total_seconds() > self._ttl_seconds:
                return None
            return deepcopy(record.payload)

    def set(self, key: str, payload: dict) -> None:
        with self._session_factory() as session:
            record = session.get(PricingCacheRecord, key)
            if record is None:
                session.add(
                    PricingCacheRecord(
                        cache_key=key,
                        payload=deepcopy(payload),
                        fetched_at=self._clock.now(),
                        source="aws_pricing_api",
                    )
                )
            else:
                record.payload = deepcopy(payload)
                record.fetched_at = self._clock.now()
                record.source = "aws_pricing_api"
            session.commit()
