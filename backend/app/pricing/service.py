import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from app.core.clock import Clock
from app.core.enums import CostConfidence
from app.models import (
    AppSettings,
    EbsVolumePricingRequest,
    ElasticIpPricingRequest,
    PricingRequest,
    PricingResult,
    SnapshotPricingRequest,
    StoppedInstancePricingRequest,
)
from app.providers.base import CloudProvider


class PricingBackend(Protocol):
    def estimate(self, request: PricingRequest) -> PricingResult: ...


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


class FallbackTableBackend:
    def __init__(self, path: str | Path | None = None) -> None:
        table_path = Path(path) if path else Path(__file__).with_name("fallback_prices.json")
        with table_path.open(encoding="utf-8") as handle:
            self._table = json.load(handle)
        self._captured_at = datetime.fromisoformat(self._table["captured_at"]).replace(tzinfo=UTC)

    def _region_prices(self, region: str) -> tuple[dict, str | None]:
        regions = self._table["regions"]
        if region in regions:
            return regions[region], None
        return regions["us-east-1"], (
            f"No fallback entry exists for {region}; us-east-1 list prices were used."
        )

    def _result(
        self,
        amount: Decimal,
        lines: list[dict],
        region_note: str | None,
        extra_note: str | None = None,
        confidence: CostConfidence = CostConfidence.MEDIUM,
        upper_bound: bool = False,
    ) -> PricingResult:
        notes = [
            *(line["label"] for line in lines),
            f"Fallback table captured at {self._table['captured_at']}.",
        ]
        if region_note:
            notes.append(region_note)
        if extra_note:
            notes.append(extra_note)
        return PricingResult(
            estimated_monthly_cost=amount,
            cost_confidence=confidence,
            explanation=" ".join(notes),
            source="fallback_table",
            pricing_timestamp=self._captured_at,
            line_items=lines,
            upper_bound=upper_bound,
        )

    def _line(
        self, label: str, quantity: Decimal, unit: str, unit_price: Decimal
    ) -> dict[str, object]:
        return {
            "label": label,
            "quantity": quantity,
            "unit": unit,
            "unit_price": unit_price,
            "monthly_cost": quantity * unit_price,
        }

    def _ebs(self, request: EbsVolumePricingRequest) -> PricingResult:
        prices, region_note = self._region_prices(request.region)
        if request.volume_type not in prices or request.volume_type.startswith("snapshot_"):
            return PricingResult(
                estimated_monthly_cost=None,
                cost_confidence=CostConfidence.UNAVAILABLE,
                explanation=(
                    f"Volume type {request.volume_type!r} is not present in the fallback table."
                ),
                source="unavailable",
                pricing_timestamp=None,
                line_items=[],
            )
        volume = prices[request.volume_type]
        size = Decimal(request.size_gib)
        lines = [
            self._line(
                f"{request.volume_type} storage: {request.size_gib} GiB",
                size,
                "GiB-month",
                _decimal(volume["storage"]),
            )
        ]
        if request.volume_type == "gp3":
            iops = Decimal(max((request.iops or 0) - 3000, 0))
            throughput = Decimal(max((request.throughput_mibps or 0) - 125, 0))
            if iops:
                lines.append(
                    self._line(
                        "gp3 provisioned IOPS above 3000",
                        iops,
                        "IOPS-month",
                        _decimal(volume["iops"]),
                    )
                )
            if throughput:
                lines.append(
                    self._line(
                        "gp3 throughput above 125 MiB/s",
                        throughput,
                        "MiB/s-month",
                        _decimal(volume["throughput"]),
                    )
                )
        elif request.volume_type == "io1":
            lines.append(
                self._line(
                    "io1 provisioned IOPS",
                    Decimal(request.iops or 0),
                    "IOPS-month",
                    _decimal(volume["iops"]),
                )
            )
        elif request.volume_type == "io2":
            remaining = request.iops or 0
            tiers = volume["iops_tiers"]
            for label, tier_quantity, tier_price in (
                ("io2 IOPS tier 1", min(remaining, 32000), tiers[0]),
                ("io2 IOPS tier 2", min(max(remaining - 32000, 0), 32000), tiers[1]),
                ("io2 IOPS tier 3", max(remaining - 64000, 0), tiers[2]),
            ):
                if tier_quantity:
                    lines.append(
                        self._line(
                            label,
                            Decimal(tier_quantity),
                            "IOPS-month",
                            _decimal(tier_price),
                        )
                    )
        extra = (
            "Magnetic standard per-I/O charges are excluded."
            if request.volume_type == "standard"
            else None
        )
        return self._result(
            sum((_decimal(line["monthly_cost"]) for line in lines), Decimal("0")),
            lines,
            region_note,
            extra,
        )

    def estimate(self, request: PricingRequest) -> PricingResult:
        if isinstance(request, EbsVolumePricingRequest):
            return self._ebs(request)
        prices, region_note = self._region_prices(request.region)
        if isinstance(request, ElasticIpPricingRequest):
            line = self._line(
                "Public IPv4 address: 730 hours",
                Decimal(730),
                "hour",
                _decimal(prices["public_ipv4_hourly"]),
            )
            return self._result(_decimal(line["monthly_cost"]), [line], region_note)
        if isinstance(request, SnapshotPricingRequest):
            tier = "snapshot_archive" if request.storage_tier == "archive" else "snapshot_standard"
            line = self._line(
                f"{request.storage_tier} snapshot upper bound: {request.size_gib} GiB",
                Decimal(request.size_gib),
                "GiB-month",
                _decimal(prices[tier]),
            )
            return self._result(
                _decimal(line["monthly_cost"]),
                [line],
                region_note,
                "Snapshots are incremental; exact reclaimable storage is unknown.",
                confidence=CostConfidence.LOW,
                upper_bound=True,
            )
        if isinstance(request, StoppedInstancePricingRequest):
            lines: list[dict] = []
            total = Decimal("0")
            for volume_request in request.volumes:
                result = self._ebs(volume_request)
                if result.estimated_monthly_cost is not None:
                    total += result.estimated_monthly_cost
                    lines.extend(result.line_items)
            if request.public_ipv4_count:
                eip_line = self._line(
                    "Public IPv4 addresses",
                    Decimal(request.public_ipv4_count * 730),
                    "hour",
                    _decimal(prices["public_ipv4_hourly"]),
                )
                total += _decimal(eip_line["monthly_cost"])
                lines.append(eip_line)
            return self._result(
                total,
                lines,
                region_note,
                "Stopped compute is not billed and is not counted.",
            )
        raise TypeError(f"unsupported pricing request: {type(request)!r}")


class PricingService:
    def __init__(
        self,
        provider: CloudProvider | None,
        settings: AppSettings,
        clock: Clock,
        cache: object | None = None,
    ) -> None:
        self._provider = provider
        self._settings = settings
        self._clock = clock
        self._cache = cache
        self._fallback = FallbackTableBackend()

    def estimate(self, request: PricingRequest) -> PricingResult:
        if self._settings.pricing_mode == "disabled":
            return PricingResult(
                estimated_monthly_cost=None,
                cost_confidence=CostConfidence.UNAVAILABLE,
                explanation="Pricing is disabled.",
                source="unavailable",
                pricing_timestamp=None,
                line_items=[],
            )
        return self._fallback.estimate(request)
