from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import (
    CostConfidence,
    DetectorType,
    FindingStatus,
    OwnershipStatus,
    PersistenceState,
    ScriptKind,
)
from app.models import AppSettings
from app.persistence.models import Finding
from app.remediation.eligibility import (
    SCRIPT_UNAVAILABLE_TEXT,
    ScriptUnavailableReason,
    script_kind_for,
)
from app.services.narrative import observation_sentence


class ObservationHistory(BaseModel):
    resource_created_at: datetime | None
    first_observed_at: datetime
    last_observed_at: datetime
    observation_count: int
    consecutive_observations: int
    streak_started_at: datetime
    persistence_state: str
    threshold_days: int
    days_until_persistent: int | None


class EstimatedCost(BaseModel):
    amount: Decimal | None
    confidence: str
    explanation: str
    source: str
    upper_bound: bool


class CleanupPlan(BaseModel):
    finding_id: UUID
    resource_id: str
    resource_type: str
    detector_type: str
    account_id: str
    region: str
    plain_language_summary: str
    reason: str
    evidence: dict[str, Any]
    observation_history: ObservationHistory
    known_dependencies: list[dict[str, Any]]
    ownership: dict[str, Any]
    estimated_cost: EstimatedCost
    detection_confidence: str
    remediation_risk: str
    preconditions: list[str]
    warnings: list[str]
    limitations: list[str]
    recommended_action: str
    script_available: bool
    script_kind: ScriptKind
    script_unavailable_reason: ScriptUnavailableReason | None


def _preconditions(finding: Finding, settings: AppSettings) -> list[str]:
    detector = DetectorType(finding.detector_type)
    if detector == DetectorType.UNATTACHED_EBS_VOLUME:
        return [
            "Volume must still be in state available with 0 attachments at execution time",
            f"Tag {settings.ignore_tag_key} must not equal {settings.ignore_tag_value}",
            "No aws:cloudformation:stack-name tag may be present",
            f"Caller account must equal {finding.account_id}",
        ]
    if detector == DetectorType.UNASSOCIATED_ELASTIC_IP:
        return [
            "Elastic IP must still have no association, instance or network interface "
            "at execution time",
            f"Tag {settings.ignore_tag_key} must not equal {settings.ignore_tag_value}",
            "No aws:cloudformation:stack-name tag may be present",
            f"Caller account must equal {finding.account_id}",
        ]
    if detector == DetectorType.STOPPED_EC2_INSTANCE:
        return [
            "Confirm with the owner whether the instance is still needed",
            "Evaluate attached volumes and Elastic IPs separately",
        ]
    return [
        "Confirm no registered AMI references the snapshot",
        "Confirm the snapshot is not shared or public",
        "Confirm no backup plan or lock depends on it",
        "Understand that reclaimed storage may be smaller than the snapshot size",
    ]


def _warnings(finding: Finding) -> list[str]:
    warnings: list[str] = []
    if finding.ownership.get("status") in {
        OwnershipStatus.CONFIRMED.value,
        OwnershipStatus.LIKELY.value,
    }:
        warnings.extend(str(note) for note in finding.ownership.get("notes", []))
    warnings.extend(
        str(dependency.get("description", "Known dependency blocks remediation."))
        for dependency in finding.known_dependencies
        if dependency.get("blocks_remediation")
    )
    if finding.cost_confidence == CostConfidence.LOW.value:
        warnings.append("The cost estimate is low confidence and may be an upper bound.")
    elif finding.cost_confidence == CostConfidence.UNAVAILABLE.value:
        warnings.append("No cost estimate is available.")
    if finding.status != FindingStatus.OPEN.value:
        warnings.append(f"The finding status is {finding.status}; remediation is disabled.")
    return warnings


def _recommended_action(
    finding: Finding,
    settings: AppSettings,
    reason: ScriptUnavailableReason | None,
    days_remaining: int,
) -> str:
    detector = DetectorType(finding.detector_type)
    if finding.status != FindingStatus.OPEN.value:
        return f"No action: finding is {finding.status}."
    if finding.ownership.get("status") == OwnershipStatus.CONFIRMED.value:
        stack_name = finding.ownership.get("stack_name") or "the owning stack"
        return (
            f"Change the CloudFormation stack {stack_name} instead of deleting the resource "
            "manually."
        )
    blocking = [
        str(item.get("description", "Known dependency"))
        for item in finding.known_dependencies
        if item.get("blocks_remediation")
    ]
    if blocking:
        return f"Resolve the blocking dependency first: {'; '.join(blocking)}."
    if detector == DetectorType.STOPPED_EC2_INSTANCE:
        return "Investigate with the owner; CloudZombie does not generate termination commands."
    if detector == DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME:
        return (
            "Investigate AMI, sharing, backup and lock status; deletion stays disabled in "
            "generated scripts."
        )
    if reason == ScriptUnavailableReason.NEWLY_OBSERVED:
        threshold = settings.thresholds_days[detector]
        return (
            f"Keep observing. This becomes a cleanup candidate after {threshold} days of "
            f"observed persistence ({days_remaining} days remaining)."
        )
    if reason is None:
        return (
            "Review the evidence, then run the guarded script; it re-validates account, "
            "region and live state before acting."
        )
    return SCRIPT_UNAVAILABLE_TEXT[reason]


def build_cleanup_plan(finding: Finding, settings: AppSettings, now: datetime) -> CleanupPlan:
    detector = DetectorType(finding.detector_type)
    threshold = settings.thresholds_days[detector]
    observation_age = (finding.last_observed_at - finding.streak_started_at).days
    persistent = finding.persistence_state == PersistenceState.PERSISTENT.value
    days_until = None if persistent else max(threshold - observation_age, 0)
    script_kind, unavailable_reason = script_kind_for(finding)
    limitations = [
        "Condition start time is not available from AWS; CloudZombie reports its own "
        "observation history instead.",
        "Dependency checks cover only known relationships (see Known dependencies).",
        "Terraform ownership is unknown unless explicit metadata says otherwise.",
        "Cost figures are public list-price estimates, not your bill.",
    ]
    snapshot = detector == DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME
    if snapshot:
        limitations.append(
            "Snapshots are incremental; exact reclaimable storage cannot be determined."
        )
    return CleanupPlan(
        finding_id=finding.id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        detector_type=finding.detector_type,
        account_id=finding.account_id,
        region=finding.region,
        plain_language_summary=(f"{finding.summary} {observation_sentence(finding, now)}"),
        reason=(
            "Guarded remediation is available."
            if unavailable_reason is None
            else SCRIPT_UNAVAILABLE_TEXT[unavailable_reason]
        ),
        evidence=finding.evidence,
        observation_history=ObservationHistory(
            resource_created_at=finding.resource_created_at,
            first_observed_at=finding.first_observed_at,
            last_observed_at=finding.last_observed_at,
            observation_count=finding.observation_count,
            consecutive_observations=finding.consecutive_observations,
            streak_started_at=finding.streak_started_at,
            persistence_state=finding.persistence_state,
            threshold_days=threshold,
            days_until_persistent=days_until,
        ),
        known_dependencies=finding.known_dependencies,
        ownership=finding.ownership,
        estimated_cost=EstimatedCost(
            amount=finding.estimated_monthly_cost,
            confidence=finding.cost_confidence,
            explanation=finding.cost_explanation,
            source=finding.pricing_source,
            upper_bound=snapshot,
        ),
        detection_confidence=finding.detection_confidence,
        remediation_risk=finding.remediation_risk,
        preconditions=_preconditions(finding, settings),
        warnings=_warnings(finding),
        limitations=limitations,
        recommended_action=_recommended_action(
            finding, settings, unavailable_reason, days_until or 0
        ),
        script_available=script_kind == ScriptKind.GUARDED_REMEDIATION,
        script_kind=script_kind,
        script_unavailable_reason=unavailable_reason,
    )
