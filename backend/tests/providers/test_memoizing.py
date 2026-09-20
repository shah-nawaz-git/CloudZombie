import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.providers.demo import DemoProvider
from app.providers.errors import ProviderPermissionError
from app.providers.memoizing import ScanScopedProvider


class CountingProvider(DemoProvider):
    def __init__(self, dataset, *, fail=False, delay=False):
        super().__init__(dataset, 5, datetime(2026, 9, 20, tzinfo=UTC))
        self.calls: dict[str, int] = {}
        self.fail = fail
        self.delay = delay
        self.error = ProviderPermissionError("ec2:DescribeVolumes", "us-east-1")

    def list_volumes(self, region):
        self.calls[region] = self.calls.get(region, 0) + 1
        if self.delay:
            time.sleep(0.02)
        if self.fail:
            raise self.error
        return super().list_volumes(region)


def test_second_call_does_not_hit_inner_provider(demo_dataset) -> None:
    inner = CountingProvider(demo_dataset)
    provider = ScanScopedProvider(inner)
    assert provider.list_volumes("us-east-1") is provider.list_volumes("us-east-1")
    assert inner.calls == {"us-east-1": 1}


def test_provider_error_instance_is_cached(demo_dataset) -> None:
    inner = CountingProvider(demo_dataset, fail=True)
    provider = ScanScopedProvider(inner)
    with pytest.raises(ProviderPermissionError) as first:
        provider.list_volumes("us-east-1")
    with pytest.raises(ProviderPermissionError) as second:
        provider.list_volumes("us-east-1")
    assert first.value is second.value is inner.error
    assert inner.calls == {"us-east-1": 1}


def test_different_regions_are_independent(demo_dataset) -> None:
    inner = CountingProvider(demo_dataset)
    provider = ScanScopedProvider(inner)
    provider.list_volumes("us-east-1")
    provider.list_volumes("eu-central-1")
    assert inner.calls == {"us-east-1": 1, "eu-central-1": 1}


def test_concurrent_calls_load_once(demo_dataset) -> None:
    inner = CountingProvider(demo_dataset, delay=True)
    provider = ScanScopedProvider(inner)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: provider.list_volumes("us-east-1"), range(8)))
    assert all(result is results[0] for result in results)
    assert inner.calls == {"us-east-1": 1}
