from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.enums import (
    CostConfidence,
    DetectionConfidence,
    DetectorCoverageStatus,
    DetectorType,
    OwnershipStatus,
    RegionCoverageStatus,
    ResourceType,
)

SAFE_TAG_PATTERN = r"^[A-Za-z0-9_.:/+@-]{1,128}$"


class AppSettings(BaseModel):
    regions: list[str] | None = None
    thresholds_days: dict[DetectorType, int] = Field(
        default_factory=lambda: {
            DetectorType.UNATTACHED_EBS_VOLUME: 7,
            DetectorType.UNASSOCIATED_ELASTIC_IP: 1,
            DetectorType.STOPPED_EC2_INSTANCE: 7,
            DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME: 30,
        }
    )
    min_consecutive_observations: int = Field(default=2, ge=1)
    ignore_tag_key: str = Field(default="cloudzombie:ignore", pattern=SAFE_TAG_PATTERN)
    ignore_tag_value: str = Field(default="true", pattern=SAFE_TAG_PATTERN)
    ignore_reason_tag_key: str = Field(default="cloudzombie:reason", pattern=SAFE_TAG_PATTERN)
    pricing_mode: Literal["auto", "fallback_only", "disabled"] = "auto"
    pricing_cache_ttl_seconds: int = Field(default=86400, ge=0)
    max_region_concurrency: int = Field(default=3, ge=1)
    demo_anchor_at: datetime | None = None

    @field_validator("demo_anchor_at")
    @classmethod
    def demo_anchor_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("demo_anchor_at must be timezone-aware")
        return value


class KnownDependency(BaseModel):
    kind: str
    target_id: str | None = None
    description: str
    blocks_remediation: bool


class Ownership(BaseModel):
    status: OwnershipStatus = OwnershipStatus.UNKNOWN
    stack_name: str | None = None
    stack_id: str | None = None
    logical_id: str | None = None
    source: Literal["stack_resource_index", "tags"] | None = None
    terraform: Literal["UNKNOWN"] = "UNKNOWN"
    notes: list[str] = Field(default_factory=list)


class EbsVolumePricingRequest(BaseModel):
    kind: Literal["ebs_volume"] = "ebs_volume"
    region: str
    volume_type: str
    size_gib: int
    iops: int | None = None
    throughput_mibps: int | None = None


class ElasticIpPricingRequest(BaseModel):
    kind: Literal["elastic_ip"] = "elastic_ip"
    region: str


class SnapshotPricingRequest(BaseModel):
    kind: Literal["snapshot"] = "snapshot"
    region: str
    size_gib: int
    storage_tier: str


class StoppedInstancePricingRequest(BaseModel):
    kind: Literal["stopped_instance"] = "stopped_instance"
    region: str
    volumes: list[EbsVolumePricingRequest]
    public_ipv4_count: int


PricingRequest = Annotated[
    EbsVolumePricingRequest
    | ElasticIpPricingRequest
    | SnapshotPricingRequest
    | StoppedInstancePricingRequest,
    Field(discriminator="kind"),
]


class PricingResult(BaseModel):
    estimated_monthly_cost: Decimal | None
    cost_confidence: CostConfidence
    explanation: str
    source: Literal["aws_pricing_api", "fallback_table", "unavailable"]
    pricing_timestamp: datetime | None
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    upper_bound: bool = False
    warnings: list[str] = Field(default_factory=list)


class FindingCandidate(BaseModel):
    account_id: str
    region: str
    resource_type: ResourceType
    resource_id: str
    detector_type: DetectorType
    title: str
    summary: str
    resource_created_at: datetime | None = None
    evidence: dict[str, Any]
    known_dependencies: list[KnownDependency] = Field(default_factory=list)
    related_resource_ids: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    ignored: bool = False
    ignore_reason: str | None = None
    pricing_request: PricingRequest | None = None
    detection_confidence: DetectionConfidence = DetectionConfidence.HIGH
    warnings: list[str] = Field(default_factory=list)
    ownership: Ownership = Field(default_factory=Ownership)
    pricing_result: PricingResult | None = None


class CoverageCell(BaseModel):
    status: DetectorCoverageStatus
    error_code: str | None = None
    message: str | None = None
    missing_operation: str | None = None


class RegionCoverage(BaseModel):
    status: RegionCoverageStatus
    detectors: dict[DetectorType, CoverageCell] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
