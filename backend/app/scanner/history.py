from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import (
    CostConfidence,
    DetectorCoverageStatus,
    DetectorType,
    FindingStatus,
    PersistenceState,
)
from app.models import AppSettings, FindingCandidate
from app.persistence.models import Finding, FindingObservation, Scan
from app.persistence.repositories import get_finding_by_identity, list_findings_for_cell
from app.scanner.classification import classify_remediation_risk


@dataclass(frozen=True)
class ReconciliationResult:
    new: int
    persistent: int
    resolved: int
    ignored: int
    observed_findings: tuple[Finding, ...]


def compute_persistence(finding: Finding, settings: AppSettings) -> PersistenceState:
    age_days = (finding.last_observed_at - finding.streak_started_at).days
    threshold = settings.thresholds_days[DetectorType(finding.detector_type)]
    if (
        age_days >= threshold
        and finding.consecutive_observations >= settings.min_consecutive_observations
    ):
        return PersistenceState.PERSISTENT
    return PersistenceState.NEWLY_OBSERVED


def _pricing_values(candidate: FindingCandidate) -> dict[str, Any]:
    result = candidate.pricing_result
    if result is None:
        return {
            "cost_confidence": CostConfidence.UNAVAILABLE.value,
            "estimated_monthly_cost": None,
            "cost_explanation": "Pricing was unavailable.",
            "pricing_source": "unavailable",
            "pricing_timestamp": None,
            "cost_line_items": [],
        }
    return {
        "cost_confidence": result.cost_confidence.value,
        "estimated_monthly_cost": result.estimated_monthly_cost,
        "cost_explanation": result.explanation,
        "pricing_source": result.source,
        "pricing_timestamp": result.pricing_timestamp,
        "cost_line_items": result.model_dump(mode="json")["line_items"],
    }


def _refresh_finding(finding: Finding, candidate: FindingCandidate, observed_at: datetime) -> None:
    finding.title = candidate.title
    finding.summary = candidate.summary
    finding.resource_created_at = candidate.resource_created_at
    finding.evidence = candidate.evidence
    finding.known_dependencies = [
        item.model_dump(mode="json") for item in candidate.known_dependencies
    ]
    finding.ownership = candidate.ownership.model_dump(mode="json")
    finding.related_resource_ids = candidate.related_resource_ids
    finding.ignore_reason = candidate.ignore_reason
    finding.detection_confidence = candidate.detection_confidence.value
    for key, value in _pricing_values(candidate).items():
        setattr(finding, key, value)
    finding.updated_at = observed_at


def reconcile(
    session: Session,
    scan: Scan,
    region: str,
    detector_type: DetectorType,
    candidates: list[FindingCandidate],
    coverage_status: DetectorCoverageStatus,
    settings: AppSettings,
    observed_at: datetime,
) -> ReconciliationResult:
    if coverage_status != DetectorCoverageStatus.COMPLETE:
        return ReconciliationResult(0, 0, 0, 0, ())

    existing = list_findings_for_cell(session, scan.account_id or "", region, detector_type)
    observed_ids: set[object] = set()
    observed: list[Finding] = []
    new_count = 0
    persistent_count = 0
    ignored_count = 0

    for candidate in candidates:
        finding = get_finding_by_identity(
            session,
            candidate.account_id,
            candidate.region,
            candidate.resource_type.value,
            candidate.resource_id,
            candidate.detector_type.value,
        )
        if finding is None:
            finding = Finding(
                account_id=candidate.account_id,
                region=candidate.region,
                resource_type=candidate.resource_type.value,
                resource_id=candidate.resource_id,
                detector_type=candidate.detector_type.value,
                title=candidate.title,
                summary=candidate.summary,
                resource_created_at=candidate.resource_created_at,
                first_observed_at=observed_at,
                last_observed_at=observed_at,
                streak_started_at=observed_at,
                observation_count=1,
                consecutive_observations=1,
                persistence_state=PersistenceState.NEWLY_OBSERVED.value,
                detection_confidence=candidate.detection_confidence.value,
                remediation_risk="REVIEW",
                cost_confidence=CostConfidence.UNAVAILABLE.value,
                evidence=candidate.evidence,
                known_dependencies=[],
                ownership={},
                related_resource_ids=candidate.related_resource_ids,
                status=(FindingStatus.IGNORED if candidate.ignored else FindingStatus.OPEN).value,
                ignore_reason=candidate.ignore_reason,
                first_scan_id=scan.id,
                last_scan_id=scan.id,
                created_at=observed_at,
                updated_at=observed_at,
            )
            session.add(finding)
            session.flush()
            new_count += 1
        else:
            if finding.status == FindingStatus.RESOLVED.value:
                finding.status = (
                    FindingStatus.IGNORED if candidate.ignored else FindingStatus.OPEN
                ).value
                finding.consecutive_observations = 1
                finding.streak_started_at = observed_at
                finding.resolved_at = None
            else:
                finding.consecutive_observations += 1
                if finding.status != FindingStatus.DISMISSED.value:
                    finding.status = (
                        FindingStatus.IGNORED if candidate.ignored else FindingStatus.OPEN
                    ).value
            finding.last_observed_at = observed_at
            finding.observation_count += 1
            finding.last_scan_id = scan.id
        _refresh_finding(finding, candidate, observed_at)
        persistence = compute_persistence(finding, settings)
        finding.persistence_state = persistence.value
        finding.remediation_risk = classify_remediation_risk(
            detector_type,
            persistence,
            candidate.ownership,
            candidate.known_dependencies,
        ).value
        session.add(
            FindingObservation(
                finding_id=finding.id,
                scan_id=scan.id,
                observed_at=observed_at,
                status_at_observation=finding.status,
                persistence_state_at_observation=finding.persistence_state,
                remediation_risk_at_observation=finding.remediation_risk,
                estimated_monthly_cost=finding.estimated_monthly_cost,
                evidence=finding.evidence,
            )
        )
        observed_ids.add(finding.id)
        observed.append(finding)
        if persistence == PersistenceState.PERSISTENT:
            persistent_count += 1
        if finding.status == FindingStatus.IGNORED.value:
            ignored_count += 1

    resolved_count = 0
    for finding in existing:
        if finding.id not in observed_ids and finding.status in {
            FindingStatus.OPEN.value,
            FindingStatus.IGNORED.value,
            FindingStatus.DISMISSED.value,
        }:
            finding.status = FindingStatus.RESOLVED.value
            finding.resolved_at = observed_at
            finding.consecutive_observations = 0
            finding.updated_at = observed_at
            resolved_count += 1

    session.flush()
    return ReconciliationResult(
        new_count, persistent_count, resolved_count, ignored_count, tuple(observed)
    )
