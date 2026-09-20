from enum import StrEnum

from app.core.enums import (
    DetectorType,
    FindingStatus,
    OwnershipStatus,
    PersistenceState,
    RemediationRisk,
    ScriptKind,
)
from app.persistence.models import Finding


class ScriptUnavailableReason(StrEnum):
    NEWLY_OBSERVED = "newly_observed"
    REMEDIATION_RISK_REVIEW = "remediation_risk_review"
    REMEDIATION_RISK_HIGH = "remediation_risk_high"
    CLOUDFORMATION_OWNED = "cloudformation_owned"
    BLOCKING_DEPENDENCY = "blocking_dependency"
    FINDING_NOT_OPEN = "finding_not_open"
    DETECTOR_HAS_NO_DESTRUCTIVE_SCRIPT = "detector_has_no_destructive_script"


SCRIPT_UNAVAILABLE_TEXT: dict[ScriptUnavailableReason, str] = {
    ScriptUnavailableReason.NEWLY_OBSERVED: (
        "The condition is newly observed and has not met the persistence threshold."
    ),
    ScriptUnavailableReason.REMEDIATION_RISK_REVIEW: (
        "The finding requires human review before any remediation."
    ),
    ScriptUnavailableReason.REMEDIATION_RISK_HIGH: ("The finding has high remediation risk."),
    ScriptUnavailableReason.CLOUDFORMATION_OWNED: (
        "The resource is owned by CloudFormation; change the stack instead."
    ),
    ScriptUnavailableReason.BLOCKING_DEPENDENCY: ("A known dependency blocks remediation."),
    ScriptUnavailableReason.FINDING_NOT_OPEN: "The finding is not open.",
    ScriptUnavailableReason.DETECTOR_HAS_NO_DESTRUCTIVE_SCRIPT: (
        "This detector has no destructive script."
    ),
}


def script_kind_for(
    finding: Finding,
) -> tuple[ScriptKind, ScriptUnavailableReason | None]:
    if finding.status != FindingStatus.OPEN.value:
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.FINDING_NOT_OPEN
    detector_type = DetectorType(finding.detector_type)
    if detector_type in {
        DetectorType.STOPPED_EC2_INSTANCE,
        DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME,
    }:
        return (
            ScriptKind.INVESTIGATION,
            ScriptUnavailableReason.DETECTOR_HAS_NO_DESTRUCTIVE_SCRIPT,
        )
    if finding.ownership.get("status") == OwnershipStatus.CONFIRMED.value:
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.CLOUDFORMATION_OWNED
    if any(dependency.get("blocks_remediation") for dependency in finding.known_dependencies):
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.BLOCKING_DEPENDENCY
    if finding.persistence_state == PersistenceState.NEWLY_OBSERVED.value:
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.NEWLY_OBSERVED
    if finding.remediation_risk == RemediationRisk.HIGH.value:
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.REMEDIATION_RISK_HIGH
    if finding.remediation_risk == RemediationRisk.REVIEW.value:
        return ScriptKind.INVESTIGATION, ScriptUnavailableReason.REMEDIATION_RISK_REVIEW
    return ScriptKind.GUARDED_REMEDIATION, None
