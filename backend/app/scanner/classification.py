from app.core.enums import (
    DetectionConfidence,
    DetectorType,
    OwnershipStatus,
    PersistenceState,
    RemediationRisk,
)
from app.models import KnownDependency, Ownership

_RISK_ORDER = {
    RemediationRisk.LOW: 0,
    RemediationRisk.REVIEW: 1,
    RemediationRisk.HIGH: 2,
}


def _max_risk(first: RemediationRisk, second: RemediationRisk) -> RemediationRisk:
    return first if _RISK_ORDER[first] >= _RISK_ORDER[second] else second


def classify_remediation_risk(
    detector_type: DetectorType,
    persistence_state: PersistenceState,
    ownership: Ownership,
    known_dependencies: list[KnownDependency],
) -> RemediationRisk:
    if detector_type in {
        DetectorType.UNATTACHED_EBS_VOLUME,
        DetectorType.UNASSOCIATED_ELASTIC_IP,
    }:
        risk = (
            RemediationRisk.LOW
            if persistence_state == PersistenceState.PERSISTENT
            else RemediationRisk.REVIEW
        )
    else:
        risk = RemediationRisk.REVIEW
    if ownership.status == OwnershipStatus.CONFIRMED:
        risk = RemediationRisk.HIGH
    elif ownership.status == OwnershipStatus.LIKELY:
        risk = _max_risk(risk, RemediationRisk.REVIEW)
    if any(dependency.blocks_remediation for dependency in known_dependencies):
        risk = RemediationRisk.HIGH
    return risk


def detection_confidence_for(detector_type: DetectorType) -> DetectionConfidence:
    return DetectionConfidence.HIGH
