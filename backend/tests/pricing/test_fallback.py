from decimal import Decimal

from app.core.enums import CostConfidence
from app.models import EbsVolumePricingRequest
from app.pricing.service import FallbackTableBackend


def estimate(**kwargs):
    return FallbackTableBackend().estimate(EbsVolumePricingRequest(**kwargs))


def test_gp3_storage_only() -> None:
    result = estimate(
        region="us-east-1", volume_type="gp3", size_gib=500, iops=3000, throughput_mibps=125
    )
    assert result.estimated_monthly_cost == Decimal("40.00")
    assert result.cost_confidence == CostConfidence.MEDIUM


def test_gp3_provisioned_performance() -> None:
    result = estimate(
        region="us-east-1", volume_type="gp3", size_gib=200, iops=6000, throughput_mibps=500
    )
    assert result.estimated_monthly_cost == Decimal("46.000")


def test_gp2_eu_central() -> None:
    result = estimate(region="eu-central-1", volume_type="gp2", size_gib=100)
    assert result.estimated_monthly_cost == Decimal("11.900")


def test_io2_tiering() -> None:
    result = estimate(region="us-east-1", volume_type="io2", size_gib=1, iops=65000)
    assert result.estimated_monthly_cost == Decimal("3584.125")


def test_unknown_region_uses_us_east_prices_with_note() -> None:
    result = estimate(region="moon-1", volume_type="gp2", size_gib=100)
    assert result.estimated_monthly_cost == Decimal("10.0")
    assert "us-east-1" in result.explanation


def test_unknown_volume_type_is_unavailable() -> None:
    result = estimate(region="us-east-1", volume_type="future", size_gib=100)
    assert result.estimated_monthly_cost is None
    assert result.cost_confidence == CostConfidence.UNAVAILABLE
