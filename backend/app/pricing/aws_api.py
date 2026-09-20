import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.clock import Clock
from app.core.enums import CostConfidence
from app.models import (
    EbsVolumePricingRequest,
    ElasticIpPricingRequest,
    PricingRequest,
    PricingResult,
    SnapshotPricingRequest,
    StoppedInstancePricingRequest,
)
from app.pricing.cache import PricingCache
from app.pricing.calculator import IopsTier, UnitPrices, VolumeUnitPrices, calculate
from app.pricing.errors import PricingLookupError
from app.providers.base import CloudProvider


def _price(dimension: dict[str, Any]) -> Decimal:
    try:
        value = Decimal(str(dimension["pricePerUnit"]["USD"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise PricingLookupError("unparseable USD price dimension") from exc
    if not value.is_finite():
        raise PricingLookupError("unparseable USD price dimension")
    return value


def _range(value: object) -> int | None:
    if value in {None, "Inf"}:
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError) as exc:
        raise PricingLookupError(f"unparseable pricing range {value!r}") from exc


def _dimensions(document: dict[str, Any]) -> list[dict[str, Any]]:
    terms = document.get("terms", {}).get("OnDemand", {})
    dimensions: list[dict[str, Any]] = []
    for term in terms.values():
        dimensions.extend(term.get("priceDimensions", {}).values())
    return dimensions


def _payload(prices: UnitPrices, fetched_at: datetime) -> dict[str, Any]:
    return {
        "volumes": {
            volume_type: {
                "storage_gib_month": str(price.storage_gib_month),
                "iops_month": str(price.iops_month) if price.iops_month is not None else None,
                "throughput_mibps_month": (
                    str(price.throughput_mibps_month)
                    if price.throughput_mibps_month is not None
                    else None
                ),
                "iops_tiers": [
                    {
                        "begin": tier.begin,
                        "end": tier.end,
                        "unit_price": str(tier.unit_price),
                    }
                    for tier in price.iops_tiers
                ],
            }
            for volume_type, price in prices.volumes.items()
        },
        "snapshot_standard_gib_month": (
            str(prices.snapshot_standard_gib_month)
            if prices.snapshot_standard_gib_month is not None
            else None
        ),
        "snapshot_archive_gib_month": (
            str(prices.snapshot_archive_gib_month)
            if prices.snapshot_archive_gib_month is not None
            else None
        ),
        "public_ipv4_hourly": (
            str(prices.public_ipv4_hourly) if prices.public_ipv4_hourly is not None else None
        ),
        "fetched_at": fetched_at.isoformat(),
    }


def _from_payload(payload: dict[str, Any]) -> tuple[UnitPrices, datetime]:
    volumes = {
        volume_type: VolumeUnitPrices(
            storage_gib_month=Decimal(data["storage_gib_month"]),
            iops_month=Decimal(data["iops_month"]) if data.get("iops_month") else None,
            throughput_mibps_month=(
                Decimal(data["throughput_mibps_month"])
                if data.get("throughput_mibps_month")
                else None
            ),
            iops_tiers=tuple(
                IopsTier(item["begin"], item.get("end"), Decimal(item["unit_price"]))
                for item in data.get("iops_tiers", [])
            ),
        )
        for volume_type, data in payload.get("volumes", {}).items()
    }
    fetched_at = datetime.fromisoformat(payload["fetched_at"])
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        raise PricingLookupError("cached pricing timestamp is not timezone-aware")
    return (
        UnitPrices(
            volumes=volumes,
            snapshot_standard_gib_month=(
                Decimal(payload["snapshot_standard_gib_month"])
                if payload.get("snapshot_standard_gib_month")
                else None
            ),
            snapshot_archive_gib_month=(
                Decimal(payload["snapshot_archive_gib_month"])
                if payload.get("snapshot_archive_gib_month")
                else None
            ),
            public_ipv4_hourly=(
                Decimal(payload["public_ipv4_hourly"])
                if payload.get("public_ipv4_hourly")
                else None
            ),
        ),
        fetched_at.astimezone(UTC),
    )


class AwsPricingApiBackend:
    def __init__(self, provider: CloudProvider, clock: Clock, cache: PricingCache) -> None:
        self._provider = provider
        self._clock = clock
        self._cache = cache

    def _documents(
        self, service_code: str, region: str, filters: list[tuple[str, str]]
    ) -> list[dict]:
        return self._provider.get_prices(
            service_code,
            [("regionCode", region), *filters],
        )

    def _single_price(
        self,
        documents: list[dict],
        *,
        unit: str,
        usage_suffix: str | None = None,
        usage_contains: str | None = None,
    ) -> Decimal:
        for document in documents:
            usage = str(document.get("product", {}).get("attributes", {}).get("usagetype", ""))
            if usage_suffix and not usage.endswith(usage_suffix):
                continue
            dimensions = _dimensions(document)
            for dimension in dimensions:
                if dimension.get("unit") == unit:
                    return _price(dimension)
            if usage_contains and usage_contains in usage:
                for dimension in dimensions:
                    return _price(dimension)
        raise PricingLookupError(
            f"missing pricing dimension unit={unit} usage_suffix={usage_suffix}"
        )

    def _volume_prices(self, region: str, volume_type: str) -> VolumeUnitPrices:
        storage_documents = self._documents(
            "AmazonEC2",
            region,
            [("productFamily", "Storage"), ("volumeApiName", volume_type)],
        )
        storage = self._single_price(storage_documents, unit="GB-Mo")
        iops = None
        throughput = None
        tiers: tuple[IopsTier, ...] = ()
        if volume_type in {"gp3", "io1", "io2"}:
            operation_documents = self._documents(
                "AmazonEC2",
                region,
                [("productFamily", "System Operation"), ("volumeApiName", volume_type)],
            )
            iops_dimensions: list[dict[str, Any]] = []
            throughput_dimensions: list[dict[str, Any]] = []
            for document in operation_documents:
                usage = str(document.get("product", {}).get("attributes", {}).get("usagetype", ""))
                for dimension in _dimensions(document):
                    unit = dimension.get("unit")
                    if unit == "IOPS-Mo" or ("VolumeP-IOPS" in usage and unit != "MiBps-Mo"):
                        iops_dimensions.append(dimension)
                    if unit == "MiBps-Mo" or "VolumeP-Throughput" in usage:
                        throughput_dimensions.append(dimension)
            if volume_type == "io2":
                if not iops_dimensions:
                    raise PricingLookupError("missing io2 IOPS pricing dimensions")
                tiers = tuple(
                    sorted(
                        (
                            IopsTier(
                                _range(item.get("beginRange")) or 0,
                                _range(item.get("endRange")),
                                _price(item),
                            )
                            for item in iops_dimensions
                        ),
                        key=lambda item: item.begin,
                    )
                )
            else:
                if not iops_dimensions:
                    raise PricingLookupError(f"missing {volume_type} IOPS pricing dimension")
                iops = _price(iops_dimensions[0])
            if volume_type == "gp3":
                if not throughput_dimensions:
                    raise PricingLookupError("missing gp3 throughput pricing dimension")
                throughput = _price(throughput_dimensions[0])
        return VolumeUnitPrices(storage, iops, throughput, tiers)

    def _load(self, request: PricingRequest) -> UnitPrices:
        volumes: dict[str, VolumeUnitPrices] = {}
        snapshot_standard = None
        snapshot_archive = None
        public_ipv4 = None
        if isinstance(request, EbsVolumePricingRequest):
            volumes[request.volume_type] = self._volume_prices(request.region, request.volume_type)
        elif isinstance(request, StoppedInstancePricingRequest):
            for volume_type in {volume.volume_type for volume in request.volumes}:
                volumes[volume_type] = self._volume_prices(request.region, volume_type)
            if request.public_ipv4_count:
                public_ipv4 = self._public_ipv4_price(request.region)
        elif isinstance(request, SnapshotPricingRequest):
            documents = self._documents(
                "AmazonEC2", request.region, [("productFamily", "Storage Snapshot")]
            )
            if request.storage_tier == "archive":
                snapshot_archive = self._single_price(
                    documents, unit="GB-Mo", usage_suffix="EBS:SnapshotArchiveStorage"
                )
            else:
                snapshot_standard = self._single_price(
                    documents, unit="GB-Mo", usage_suffix="EBS:SnapshotUsage"
                )
        elif isinstance(request, ElasticIpPricingRequest):
            public_ipv4 = self._public_ipv4_price(request.region)
        return UnitPrices(
            volumes=volumes,
            snapshot_standard_gib_month=snapshot_standard,
            snapshot_archive_gib_month=snapshot_archive,
            public_ipv4_hourly=public_ipv4,
        )

    def _public_ipv4_price(self, region: str) -> Decimal:
        documents = self._documents("AmazonVPC", region, [("productFamily", "IP Address")])
        return self._single_price(documents, unit="Hrs", usage_suffix="PublicIPv4:IdleAddress")

    def estimate(self, request: PricingRequest) -> PricingResult:
        if isinstance(request, EbsVolumePricingRequest):
            identity: object = ("ebs", request.region, request.volume_type)
        elif isinstance(request, SnapshotPricingRequest):
            identity = ("snapshot", request.region, request.storage_tier)
        elif isinstance(request, ElasticIpPricingRequest):
            identity = ("elastic_ip", request.region)
        else:
            identity = (
                "stopped_instance",
                request.region,
                sorted({volume.volume_type for volume in request.volumes}),
                bool(request.public_ipv4_count),
            )
        identity_json = json.dumps(identity, sort_keys=True)
        cache_key = "aws-pricing:" + hashlib.sha256(identity_json.encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is None:
            unit_prices = self._load(request)
            fetched_at = self._clock.now()
            self._cache.set(cache_key, _payload(unit_prices, fetched_at))
        else:
            unit_prices, fetched_at = _from_payload(cached)
        amount, lines, notes = calculate(request, unit_prices)
        snapshot = isinstance(request, SnapshotPricingRequest)
        explanation = [
            *(str(line["label"]) for line in lines),
            *notes,
            f"AWS Pricing API, retrieved {fetched_at.isoformat()}",
        ]
        return PricingResult(
            estimated_monthly_cost=amount,
            cost_confidence=CostConfidence.LOW if snapshot else CostConfidence.HIGH,
            explanation=" ".join(explanation),
            source="aws_pricing_api",
            pricing_timestamp=fetched_at,
            line_items=lines,
            upper_bound=snapshot,
        )
