from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import DetectorType, ScriptKind
from app.models import AppSettings, RegionCoverage
from app.remediation.eligibility import ScriptUnavailableReason
from app.remediation.plan import CleanupPlan
from app.remediation.validators import validate_region


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(ApiModel):
    status: str
    mode: str
    database: str
    version: str


class IdentityOut(ApiModel):
    mode: str
    account_id: str | None
    principal_arn: str | None
    identity_type: str | None
    verified_at: datetime | None
    error: str | None


class ScanOut(ApiModel):
    id: UUID
    mode: str
    account_id: str | None
    principal_arn: str | None
    seeded: bool
    started_at: datetime
    finished_at: datetime | None
    status: str
    requested_regions: list[str]
    completed_regions: list[str]
    partial_regions: list[str]
    failed_regions: list[str]
    skipped_regions: list[str]
    coverage: dict[str, Any]
    new_findings: int
    persistent_findings: int
    resolved_findings: int
    ignored_findings: int
    estimated_exposure: float
    potential_exposure_low_confidence: float
    errors: list[dict[str, Any]]
    created_at: datetime


class ScanListOut(ApiModel):
    items: list[ScanOut]
    total: int


class FindingOut(ApiModel):
    id: UUID
    account_id: str
    region: str
    resource_type: str
    resource_id: str
    detector_type: str
    title: str
    summary: str
    resource_created_at: datetime | None
    first_observed_at: datetime
    last_observed_at: datetime
    streak_started_at: datetime
    observation_count: int
    consecutive_observations: int
    persistence_state: str
    detection_confidence: str
    remediation_risk: str
    cost_confidence: str
    estimated_monthly_cost: float | None
    cost_explanation: str
    pricing_source: str
    pricing_timestamp: datetime | None
    cost_line_items: list[dict[str, Any]]
    evidence: dict[str, Any]
    known_dependencies: list[dict[str, Any]]
    ownership: dict[str, Any]
    related_resource_ids: list[str]
    status: str
    resolved_at: datetime | None
    dismissed_at: datetime | None
    dismiss_reason: str | None
    ignore_reason: str | None
    first_scan_id: UUID
    last_scan_id: UUID
    created_at: datetime
    updated_at: datetime
    resource_age_days: int | None
    observation_age_days: int
    days_until_persistent: int | None
    threshold_days: int
    script_kind: ScriptKind
    script_available: bool
    script_unavailable_reason: ScriptUnavailableReason | None


class ObservationOut(ApiModel):
    scan_id: UUID
    observed_at: datetime
    status: str
    persistence_state: str
    remediation_risk: str
    estimated_monthly_cost: float | None


class RelatedFindingOut(ApiModel):
    id: UUID
    resource_id: str
    resource_type: str
    status: str


class FindingDetailOut(FindingOut):
    observations: list[ObservationOut]
    related_findings: list[RelatedFindingOut]


class FindingListOut(ApiModel):
    items: list[FindingOut]
    total: int
    page: int
    page_size: int


class FindingPatchIn(ApiModel):
    status: Literal["dismissed", "open"]
    reason: str | None = Field(default=None, max_length=500)


PlanOut = CleanupPlan


class ScriptOut(ApiModel):
    kind: ScriptKind
    filename: str
    content: str
    checks: list[str]
    warnings: list[str]
    unavailable_reason: ScriptUnavailableReason | None = None
    unavailable_text: str | None = None


class BulkScriptIn(ApiModel):
    finding_ids: list[UUID] = Field(min_length=1, max_length=200)


class BulkSkippedOut(ApiModel):
    finding_id: UUID
    reason: str


class BulkScriptOut(ApiModel):
    script: ScriptOut | None
    included: list[UUID]
    skipped: list[BulkSkippedOut]


class HistoryPoint(ApiModel):
    scan_id: UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    seeded: bool
    new_findings: int
    resolved_findings: int
    observed_findings: int
    estimated_exposure: float
    potential_exposure_low_confidence: float
    observed_by_resource_type: dict[str, int]
    exposure_by_resource_type: dict[str, float]


class HistoryOut(ApiModel):
    points: list[HistoryPoint]


class CoverageOut(ApiModel):
    scan_id: UUID
    started_at: datetime
    status: str
    regions: dict[str, RegionCoverage]
    completed_regions: list[str]
    partial_regions: list[str]
    failed_regions: list[str]
    skipped_regions: list[str]
    errors: list[dict[str, Any]]


class CoverageSummary(ApiModel):
    complete: int
    partial: int
    failed: int
    skipped: int


class OverviewOut(ApiModel):
    mode: str
    account_id: str | None
    latest_scan: ScanOut | None
    scan_running: bool
    estimated_monthly_cleanup_opportunity: float
    potential_low_confidence_exposure: float
    open_findings: int
    persistent_low_risk_candidates: int
    review_required: int
    high_risk: int
    newly_observed: int
    ignored: int
    dismissed: int
    resolved_in_latest_scan: int
    regions_scanned: list[str]
    coverage_summary: CoverageSummary
    findings_by_resource_type: dict[str, int]
    exposure_by_resource_type: dict[str, float]


DETECTOR_THRESHOLDS_HELP = {
    "unattached_ebs_volume": "Days observed before an unattached EBS volume becomes persistent.",
    "unassociated_elastic_ip": (
        "Days observed before an unassociated Elastic IP becomes persistent."
    ),
    "stopped_ec2_instance": "Observation threshold for stopped EC2 instances.",
    "snapshot_missing_source_volume": (
        "Observation threshold for snapshots with deleted source volumes."
    ),
}


class SettingsOut(AppSettings):
    mode: str
    detector_thresholds_help: dict[str, str] = DETECTOR_THRESHOLDS_HELP


class SettingsPatchIn(ApiModel):
    regions: list[str] | None = None
    thresholds_days: dict[str, int] | None = None
    min_consecutive_observations: int | None = Field(default=None, ge=1)
    ignore_tag_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:/+@-]{1,128}$")
    ignore_tag_value: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:/+@-]{1,256}$")
    ignore_reason_tag_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:/+@-]{1,128}$")
    pricing_mode: Literal["auto", "fallback_only", "disabled"] | None = None
    pricing_cache_ttl_seconds: int | None = Field(default=None, ge=0)
    max_region_concurrency: int | None = Field(default=None, ge=1, le=8)

    @field_validator("regions")
    @classmethod
    def regions_are_valid(cls, value: list[str] | None) -> list[str] | None:
        if value is not None:
            for region in value:
                validate_region(region)
        return value

    @field_validator("thresholds_days")
    @classmethod
    def thresholds_are_non_negative(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is not None:
            if any(days < 0 for days in value.values()):
                raise ValueError("thresholds must be non-negative")
            allowed = {item.value for item in DetectorType}
            if set(value) - allowed:
                raise ValueError("unknown detector threshold")
        return value


class ScanCreateIn(ApiModel):
    regions: list[str] | None = None
    wait: bool = False

    @field_validator("regions")
    @classmethod
    def scan_regions_are_valid(cls, value: list[str] | None) -> list[str] | None:
        if value is not None:
            for region in value:
                validate_region(region)
        return value
