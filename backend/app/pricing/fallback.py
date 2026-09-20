import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.core.enums import CostConfidence
from app.models import PricingRequest, PricingResult, SnapshotPricingRequest
from app.pricing.calculator import IopsTier, UnitPrices, VolumeUnitPrices, calculate
from app.pricing.errors import PricingLookupError


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


class FallbackTableBackend:
    def __init__(self, path: str | Path | None = None) -> None:
        table_path = Path(path) if path else Path(__file__).with_name("fallback_prices.json")
        with table_path.open(encoding="utf-8") as handle:
            self._table = json.load(handle)
        self._captured_at = datetime.fromisoformat(self._table["captured_at"]).replace(tzinfo=UTC)

    def _unit_prices(self, region: str) -> tuple[UnitPrices, str | None]:
        regions = self._table["regions"]
        region_note = None
        if region not in regions:
            region_note = f"No fallback entry exists for {region}; us-east-1 list prices were used."
            region = "us-east-1"
        prices = regions[region]
        volumes: dict[str, VolumeUnitPrices] = {}
        for volume_type in ("gp3", "gp2", "io1", "io2", "st1", "sc1", "standard"):
            volume = prices[volume_type]
            tiers: tuple[IopsTier, ...] = ()
            if "iops_tiers" in volume:
                tiers = (
                    IopsTier(0, 32000, _decimal(volume["iops_tiers"][0])),
                    IopsTier(32000, 64000, _decimal(volume["iops_tiers"][1])),
                    IopsTier(64000, None, _decimal(volume["iops_tiers"][2])),
                )
            volumes[volume_type] = VolumeUnitPrices(
                storage_gib_month=_decimal(volume["storage"]),
                iops_month=_decimal(volume["iops"]) if "iops" in volume else None,
                throughput_mibps_month=(
                    _decimal(volume["throughput"]) if "throughput" in volume else None
                ),
                iops_tiers=tiers,
            )
        return (
            UnitPrices(
                volumes=volumes,
                snapshot_standard_gib_month=_decimal(prices["snapshot_standard"]),
                snapshot_archive_gib_month=_decimal(prices["snapshot_archive"]),
                public_ipv4_hourly=_decimal(prices["public_ipv4_hourly"]),
            ),
            region_note,
        )

    def estimate(self, request: PricingRequest) -> PricingResult:
        unit_prices, region_note = self._unit_prices(request.region)
        try:
            amount, lines, notes = calculate(request, unit_prices)
        except PricingLookupError as exc:
            return PricingResult(
                estimated_monthly_cost=None,
                cost_confidence=CostConfidence.UNAVAILABLE,
                explanation=str(exc),
                source="unavailable",
                pricing_timestamp=None,
                line_items=[],
            )
        explanation = [
            *(str(line["label"]) for line in lines),
            *notes,
            f"Fallback table captured at {self._table['captured_at']}.",
        ]
        if region_note:
            explanation.append(region_note)
        snapshot = isinstance(request, SnapshotPricingRequest)
        return PricingResult(
            estimated_monthly_cost=amount,
            cost_confidence=CostConfidence.LOW if snapshot else CostConfidence.MEDIUM,
            explanation=" ".join(explanation),
            source="fallback_table",
            pricing_timestamp=self._captured_at,
            line_items=lines,
            upper_bound=snapshot,
        )
