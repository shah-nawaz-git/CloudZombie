from collections.abc import Callable, Sequence
from threading import Lock
from typing import TypeVar

from app.providers.base import (
    Address,
    CloudProvider,
    Identity,
    Image,
    Instance,
    RegionInfo,
    Snapshot,
    SnapshotAttributes,
    SnapshotLock,
    StackResource,
    Volume,
)
from app.providers.errors import ProviderError

T = TypeVar("T")


class ScanScopedProvider(CloudProvider):
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider
        self.mode = provider.mode
        self._cache: dict[tuple[str, str | None], object] = {}
        self._locks: dict[tuple[str, str | None], Lock] = {}
        self._locks_guard = Lock()

    def _lock_for(self, key: tuple[str, str | None]) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, Lock())

    def _memoize(self, key: tuple[str, str | None], load: Callable[[], T]) -> T:
        with self._lock_for(key):
            if key in self._cache:
                cached = self._cache[key]
                if isinstance(cached, ProviderError):
                    raise cached
                return cached  # type: ignore[return-value]
            try:
                value = load()
            except ProviderError as exc:
                self._cache[key] = exc
                raise
            self._cache[key] = value
            return value

    def get_identity(self) -> Identity:
        return self._memoize(("get_identity", None), self._provider.get_identity)

    def list_regions(self) -> list[RegionInfo]:
        return self._memoize(("list_regions", None), self._provider.list_regions)

    def list_volumes(self, region: str) -> list[Volume]:
        return self._memoize(("list_volumes", region), lambda: self._provider.list_volumes(region))

    def list_addresses(self, region: str) -> list[Address]:
        return self._memoize(
            ("list_addresses", region), lambda: self._provider.list_addresses(region)
        )

    def list_instances(self, region: str) -> list[Instance]:
        return self._memoize(
            ("list_instances", region), lambda: self._provider.list_instances(region)
        )

    def list_snapshots(self, region: str) -> list[Snapshot]:
        return self._memoize(
            ("list_snapshots", region), lambda: self._provider.list_snapshots(region)
        )

    def list_images(self, region: str) -> list[Image]:
        return self._memoize(("list_images", region), lambda: self._provider.list_images(region))

    def get_snapshot_attributes(self, region: str, snapshot_id: str) -> SnapshotAttributes:
        return self._provider.get_snapshot_attributes(region, snapshot_id)

    def get_snapshot_locks(self, region: str, snapshot_ids: Sequence[str]) -> list[SnapshotLock]:
        return self._provider.get_snapshot_locks(region, snapshot_ids)

    def list_stack_resources(self, region: str) -> list[StackResource]:
        return self._memoize(
            ("list_stack_resources", region),
            lambda: self._provider.list_stack_resources(region),
        )

    def get_prices(self, service_code: str, filters: Sequence[tuple[str, str]]) -> list[dict]:
        return self._provider.get_prices(service_code, filters)
