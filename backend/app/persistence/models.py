from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.enums import (
    CostConfidence,
    DetectionConfidence,
    DetectorType,
    FindingStatus,
    Mode,
    PersistenceState,
    RemediationRisk,
    ResourceType,
    ScanStatus,
)
from app.persistence.types import UtcDateTime


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(16), default=Mode.DEMO.value)
    account_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    principal_arn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ScanStatus.RUNNING.value)
    requested_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    completed_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    partial_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    failed_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    skipped_regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    new_findings: Mapped[int] = mapped_column(Integer, default=0)
    persistent_findings: Mapped[int] = mapped_column(Integer, default=0)
    resolved_findings: Mapped[int] = mapped_column(Integer, default=0)
    ignored_findings: Mapped[int] = mapped_column(Integer, default=0)
    estimated_exposure: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    potential_exposure_low_confidence: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0")
    )
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "region",
            "resource_type",
            "resource_id",
            "detector_type",
            name="uq_finding_identity",
        ),
        Index("ix_findings_status", "status"),
        Index("ix_findings_region", "region"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[str] = mapped_column(String(32))
    region: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64), default=ResourceType.EBS_VOLUME.value)
    resource_id: Mapped[str] = mapped_column(String(255))
    detector_type: Mapped[str] = mapped_column(
        String(64), default=DetectorType.UNATTACHED_EBS_VOLUME.value
    )
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text)
    resource_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    first_observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    last_observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    streak_started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    observation_count: Mapped[int] = mapped_column(Integer, default=1)
    consecutive_observations: Mapped[int] = mapped_column(Integer, default=1)
    persistence_state: Mapped[str] = mapped_column(
        String(32), default=PersistenceState.NEWLY_OBSERVED.value
    )
    detection_confidence: Mapped[str] = mapped_column(
        String(16), default=DetectionConfidence.HIGH.value
    )
    remediation_risk: Mapped[str] = mapped_column(String(16), default=RemediationRisk.REVIEW.value)
    cost_confidence: Mapped[str] = mapped_column(
        String(16), default=CostConfidence.UNAVAILABLE.value
    )
    estimated_monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cost_explanation: Mapped[str] = mapped_column(Text, default="")
    pricing_source: Mapped[str] = mapped_column(String(64), default="unavailable")
    pricing_timestamp: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    cost_line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    known_dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ownership: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    related_resource_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default=FindingStatus.OPEN.value)
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    dismiss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ignore_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"))
    last_scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())

    observations: Mapped[list["FindingObservation"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return f"{self.title} ({self.status}; observed in {self.observation_count} scans)"


class FindingObservation(Base):
    __tablename__ = "finding_observations"
    __table_args__ = (
        UniqueConstraint("finding_id", "scan_id", name="uq_finding_observation_scan"),
        Index("ix_finding_observations_finding_scan", "finding_id", "scan_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    scan_id: Mapped[UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    status_at_observation: Mapped[str] = mapped_column(String(16))
    persistence_state_at_observation: Mapped[str] = mapped_column(String(32))
    remediation_risk_at_observation: Mapped[str] = mapped_column(String(16))
    estimated_monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    cost_confidence_at_observation: Mapped[str] = mapped_column(
        String(16), default=CostConfidence.UNAVAILABLE.value
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    finding: Mapped[Finding] = relationship(back_populates="observations")


class SettingsRecord(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class PricingCache(Base):
    __tablename__ = "pricing_cache"

    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime())
    source: Mapped[str] = mapped_column(String(64))
