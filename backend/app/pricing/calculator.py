from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models import (
    EbsVolumePricingRequest,
    ElasticIpPricingRequest,
    PricingRequest,
    SnapshotPricingRequest,
    StoppedInstancePricingRequest,
)
from app.pricing.errors import PricingLookupError


@dataclass(frozen=True)
class IopsTier:
    begin: int
    end: int | None
    unit_price: Decimal


@dataclass(frozen=True)
class VolumeUnitPrices:
    storage_gib_month: Decimal
    iops_month: Decimal | None = None
    throughput_mibps_month: Decimal | None = None
    iops_tiers: tuple[IopsTier, ...] = ()


@dataclass(frozen=True)
class UnitPrices:
    volumes: dict[str, VolumeUnitPrices] = field(default_factory=dict)
    snapshot_standard_gib_month: Decimal | None = None
    snapshot_archive_gib_month: Decimal | None = None
    public_ipv4_hourly: Decimal | None = None


def _line(label: str, quantity: Decimal, unit: str, unit_price: Decimal) -> dict[str, Any]:
    return {
        "label": label,
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "monthly_cost": quantity * unit_price,
    }


def _required(value: Decimal | None, label: str) -> Decimal:
    if value is None:
        raise PricingLookupError(f"missing unit price for {label}")
    return value


def _calculate_ebs(
    request: EbsVolumePricingRequest, unit_prices: UnitPrices
) -> tuple[Decimal, list[dict[str, Any]], list[str]]:
    prices = unit_prices.volumes.get(request.volume_type)
    if prices is None:
        raise PricingLookupError(f"unknown volume type {request.volume_type}")
    lines = [
        _line(
            f"{request.volume_type} storage: {request.size_gib} GiB",
            Decimal(request.size_gib),
            "GiB-month",
            prices.storage_gib_month,
        )
    ]
    notes: list[str] = []
    if request.volume_type == "gp3":
        iops = Decimal(max((request.iops or 0) - 3000, 0))
        throughput = Decimal(max((request.throughput_mibps or 0) - 125, 0))
        if iops:
            lines.append(
                _line(
                    "gp3 provisioned IOPS above 3000",
                    iops,
                    "IOPS-month",
                    _required(prices.iops_month, "gp3 IOPS"),
                )
            )
        if throughput:
            lines.append(
                _line(
                    "gp3 throughput above 125 MiB/s",
                    throughput,
                    "MiB/s-month",
                    _required(prices.throughput_mibps_month, "gp3 throughput"),
                )
            )
    elif request.volume_type == "io1":
        lines.append(
            _line(
                "io1 provisioned IOPS",
                Decimal(request.iops or 0),
                "IOPS-month",
                _required(prices.iops_month, "io1 IOPS"),
            )
        )
    elif request.volume_type == "io2":
        provisioned = request.iops or 0
        if prices.iops_tiers:
            for index, tier in enumerate(sorted(prices.iops_tiers, key=lambda item: item.begin), 1):
                upper = tier.end if tier.end is not None else provisioned
                quantity = max(min(provisioned, upper) - tier.begin, 0)
                if quantity:
                    lines.append(
                        _line(
                            f"io2 IOPS tier {index}",
                            Decimal(quantity),
                            "IOPS-month",
                            tier.unit_price,
                        )
                    )
        else:
            lines.append(
                _line(
                    "io2 provisioned IOPS",
                    Decimal(provisioned),
                    "IOPS-month",
                    _required(prices.iops_month, "io2 IOPS"),
                )
            )
    if request.volume_type == "standard":
        notes.append("Magnetic standard per-I/O charges are excluded.")
    total = sum((Decimal(str(line["monthly_cost"])) for line in lines), Decimal("0"))
    return total, lines, notes


def calculate(
    request: PricingRequest, unit_prices: UnitPrices
) -> tuple[Decimal, list[dict[str, Any]], list[str]]:
    if isinstance(request, EbsVolumePricingRequest):
        return _calculate_ebs(request, unit_prices)
    if isinstance(request, ElasticIpPricingRequest):
        line = _line(
            "Public IPv4 address: 730 hours",
            Decimal(730),
            "hour",
            _required(unit_prices.public_ipv4_hourly, "public IPv4 hourly"),
        )
        return Decimal(str(line["monthly_cost"])), [line], []
    if isinstance(request, SnapshotPricingRequest):
        price = (
            unit_prices.snapshot_archive_gib_month
            if request.storage_tier == "archive"
            else unit_prices.snapshot_standard_gib_month
        )
        line = _line(
            f"{request.storage_tier} snapshot upper bound: {request.size_gib} GiB",
            Decimal(request.size_gib),
            "GiB-month",
            _required(price, f"{request.storage_tier} snapshot storage"),
        )
        return (
            Decimal(str(line["monthly_cost"])),
            [line],
            ["Snapshots are incremental; exact reclaimable storage is unknown."],
        )
    if isinstance(request, StoppedInstancePricingRequest):
        total = Decimal("0")
        lines: list[dict[str, Any]] = []
        notes: list[str] = []
        for volume in request.volumes:
            amount, volume_lines, volume_notes = _calculate_ebs(volume, unit_prices)
            total += amount
            lines.extend(volume_lines)
            notes.extend(volume_notes)
        if request.public_ipv4_count:
            line = _line(
                "Public IPv4 addresses",
                Decimal(request.public_ipv4_count * 730),
                "hour",
                _required(unit_prices.public_ipv4_hourly, "public IPv4 hourly"),
            )
            total += Decimal(str(line["monthly_cost"]))
            lines.append(line)
        notes.append("Stopped compute is not billed and is not counted.")
        return total, lines, notes
    raise PricingLookupError(f"unsupported pricing request {type(request)!r}")
