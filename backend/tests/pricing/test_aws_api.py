from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.enums import CostConfidence
from app.models import (
    EbsVolumePricingRequest,
    ElasticIpPricingRequest,
    SnapshotPricingRequest,
)
from app.pricing.aws_api import AwsPricingApiBackend
from app.pricing.cache import InMemoryPricingCache
from app.pricing.errors import PricingLookupError


def document(family, usage, unit, price, *, volume_type=None, dimensions=None):
    attributes = {"usagetype": usage, "regionCode": "eu-central-1"}
    if volume_type:
        attributes["volumeApiName"] = volume_type
    price_dimensions = dimensions or {
        "dimension": {
            "unit": unit,
            "beginRange": "0",
            "endRange": "Inf",
            "pricePerUnit": {"USD": price},
        }
    }
    return {
        "product": {
            "productFamily": family,
            "sku": "SKU1",
            "attributes": attributes,
        },
        "serviceCode": "AmazonEC2",
        "terms": {
            "OnDemand": {
                "term": {"priceDimensions": price_dimensions},
            }
        },
    }


class FakePricingProvider:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_prices(self, service_code, filters):
        self.calls.append((service_code, tuple(filters)))
        selected = dict(filters)
        key = (service_code, selected.get("productFamily"), selected.get("volumeApiName"))
        return self.responses.get(key, [])


def backend(provider, fixed_clock, ttl=86400):
    cache = InMemoryPricingCache(fixed_clock, ttl)
    return AwsPricingApiBackend(provider, fixed_clock, cache)


def test_gp3_storage_iops_and_throughput(fixed_clock) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage", "gp3"): [
                document(
                    "Storage", "EUC1-EBS:VolumeUsage.gp3", "GB-Mo", "0.0952", volume_type="gp3"
                )
            ],
            ("AmazonEC2", "System Operation", "gp3"): [
                document(
                    "System Operation",
                    "EUC1-EBS:VolumeP-IOPS.gp3",
                    "IOPS-Mo",
                    "0.006",
                    volume_type="gp3",
                ),
                document(
                    "System Operation",
                    "EUC1-EBS:VolumeP-Throughput.gp3",
                    "MiBps-Mo",
                    "0.0476",
                    volume_type="gp3",
                ),
            ],
        }
    )
    result = backend(provider, fixed_clock).estimate(
        EbsVolumePricingRequest(
            region="eu-central-1",
            volume_type="gp3",
            size_gib=200,
            iops=6000,
            throughput_mibps=500,
        )
    )
    assert result.estimated_monthly_cost == Decimal("54.89")
    assert result.cost_confidence == CostConfidence.HIGH
    assert result.source == "aws_pricing_api"


def test_gp2_storage(fixed_clock) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage", "gp2"): [
                document("Storage", "EBS:VolumeUsage.gp2", "GB-Mo", "0.119", volume_type="gp2")
            ]
        }
    )
    result = backend(provider, fixed_clock).estimate(
        EbsVolumePricingRequest(region="eu-central-1", volume_type="gp2", size_gib=100)
    )
    assert result.estimated_monthly_cost == Decimal("11.900")


def test_io2_tiers(fixed_clock) -> None:
    dimensions = {
        "one": {
            "unit": "IOPS-Mo",
            "beginRange": "0",
            "endRange": "32000",
            "pricePerUnit": {"USD": "0.078"},
        },
        "two": {
            "unit": "IOPS-Mo",
            "beginRange": "32000",
            "endRange": "64000",
            "pricePerUnit": {"USD": "0.055"},
        },
        "three": {
            "unit": "IOPS-Mo",
            "beginRange": "64000",
            "endRange": "Inf",
            "pricePerUnit": {"USD": "0.038"},
        },
    }
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage", "io2"): [
                document("Storage", "EBS:VolumeUsage.io2", "GB-Mo", "0.149", volume_type="io2")
            ],
            ("AmazonEC2", "System Operation", "io2"): [
                document(
                    "System Operation",
                    "EBS:VolumeP-IOPS.io2",
                    "IOPS-Mo",
                    "0",
                    volume_type="io2",
                    dimensions=dimensions,
                )
            ],
        }
    )
    result = backend(provider, fixed_clock).estimate(
        EbsVolumePricingRequest(region="eu-central-1", volume_type="io2", size_gib=1, iops=65000)
    )
    assert result.estimated_monthly_cost == Decimal("4294.149")


@pytest.mark.parametrize(
    ("tier", "usage", "price"),
    [
        ("standard", "EUC1-EBS:SnapshotUsage", "0.054"),
        ("archive", "EUC1-EBS:SnapshotArchiveStorage", "0.0135"),
    ],
)
def test_snapshot_prices_are_low_confidence_upper_bounds(fixed_clock, tier, usage, price) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage Snapshot", None): [
                document("Storage Snapshot", usage, "GB-Mo", price)
            ]
        }
    )
    result = backend(provider, fixed_clock).estimate(
        SnapshotPricingRequest(region="eu-central-1", size_gib=100, storage_tier=tier)
    )
    assert result.estimated_monthly_cost == Decimal("100") * Decimal(price)
    assert result.cost_confidence == CostConfidence.LOW
    assert result.upper_bound is True


def test_public_ipv4(fixed_clock) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonVPC", "IP Address", None): [
                document("IP Address", "EUC1-PublicIPv4:IdleAddress", "Hrs", "0.005")
            ]
        }
    )
    result = backend(provider, fixed_clock).estimate(ElasticIpPricingRequest(region="eu-central-1"))
    assert result.estimated_monthly_cost == Decimal("3.650")


def test_cache_hit_avoids_provider_and_keeps_timestamp(fixed_clock) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage", "gp2"): [
                document("Storage", "EBS:VolumeUsage.gp2", "GB-Mo", "0.119", volume_type="gp2")
            ]
        }
    )
    selected = backend(provider, fixed_clock)
    request = EbsVolumePricingRequest(region="eu-central-1", volume_type="gp2", size_gib=100)
    first = selected.estimate(request)
    fixed_clock.advance_to(fixed_clock.now() + timedelta(hours=1))
    second = selected.estimate(request)
    assert len(provider.calls) == 1
    assert second.pricing_timestamp == first.pricing_timestamp


def test_expired_cache_refetches(fixed_clock) -> None:
    provider = FakePricingProvider(
        {
            ("AmazonEC2", "Storage", "gp2"): [
                document("Storage", "EBS:VolumeUsage.gp2", "GB-Mo", "0.119", volume_type="gp2")
            ]
        }
    )
    selected = backend(provider, fixed_clock, ttl=60)
    request = EbsVolumePricingRequest(region="eu-central-1", volume_type="gp2", size_gib=100)
    selected.estimate(request)
    fixed_clock.advance_to(fixed_clock.now() + timedelta(seconds=61))
    selected.estimate(request)
    assert len(provider.calls) == 2


def test_missing_product_raises_lookup_error(fixed_clock) -> None:
    with pytest.raises(PricingLookupError):
        backend(FakePricingProvider({}), fixed_clock).estimate(
            EbsVolumePricingRequest(region="eu-central-1", volume_type="gp2", size_gib=1)
        )
