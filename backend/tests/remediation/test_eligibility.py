import pytest

from app.core.enums import (
    DetectorType,
    FindingStatus,
    OwnershipStatus,
    PersistenceState,
    RemediationRisk,
    ResourceType,
    ScriptKind,
)
from app.remediation.eligibility import ScriptUnavailableReason, script_kind_for
from tests.remediation.finding_factory import make_finding


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"status": FindingStatus.DISMISSED.value}, ScriptUnavailableReason.FINDING_NOT_OPEN),
        (
            {
                "resource_type": ResourceType.EC2_INSTANCE.value,
                "resource_id": "i-0a1b2c3d4e5f60001",
                "detector_type": DetectorType.STOPPED_EC2_INSTANCE.value,
            },
            ScriptUnavailableReason.DETECTOR_HAS_NO_DESTRUCTIVE_SCRIPT,
        ),
        (
            {"ownership": {"status": OwnershipStatus.CONFIRMED.value}},
            ScriptUnavailableReason.CLOUDFORMATION_OWNED,
        ),
        (
            {
                "known_dependencies": [
                    {"kind": "x", "description": "blocking", "blocks_remediation": True}
                ]
            },
            ScriptUnavailableReason.BLOCKING_DEPENDENCY,
        ),
        (
            {
                "persistence_state": PersistenceState.NEWLY_OBSERVED.value,
                "remediation_risk": RemediationRisk.REVIEW.value,
            },
            ScriptUnavailableReason.NEWLY_OBSERVED,
        ),
        (
            {"remediation_risk": RemediationRisk.REVIEW.value},
            ScriptUnavailableReason.REMEDIATION_RISK_REVIEW,
        ),
        (
            {"remediation_risk": RemediationRisk.HIGH.value},
            ScriptUnavailableReason.REMEDIATION_RISK_HIGH,
        ),
    ],
)
def test_ineligibility_reason_priority(changes, reason) -> None:
    kind, actual = script_kind_for(make_finding(**changes))
    assert kind == ScriptKind.INVESTIGATION
    assert actual == reason


def test_persistent_low_ebs_is_guarded() -> None:
    assert script_kind_for(make_finding()) == (ScriptKind.GUARDED_REMEDIATION, None)
