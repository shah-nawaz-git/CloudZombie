import pytest

from app.core.enums import DetectorType, OwnershipStatus, PersistenceState, RemediationRisk
from app.models import KnownDependency, Ownership
from app.scanner.classification import classify_remediation_risk


@pytest.mark.parametrize(
    ("state", "ownership", "expected"),
    [
        (PersistenceState.NEWLY_OBSERVED, OwnershipStatus.UNKNOWN, RemediationRisk.REVIEW),
        (PersistenceState.PERSISTENT, OwnershipStatus.UNKNOWN, RemediationRisk.LOW),
        (PersistenceState.PERSISTENT, OwnershipStatus.CONFIRMED, RemediationRisk.HIGH),
        (PersistenceState.PERSISTENT, OwnershipStatus.LIKELY, RemediationRisk.REVIEW),
    ],
)
def test_ebs_classification(state, ownership, expected) -> None:
    assert (
        classify_remediation_risk(
            DetectorType.UNATTACHED_EBS_VOLUME,
            state,
            Ownership(status=ownership),
            [],
        )
        == expected
    )


def test_blocking_dependency_escalates_to_high() -> None:
    dependency = KnownDependency(
        kind="image", description="Referenced by an image", blocks_remediation=True
    )
    assert (
        classify_remediation_risk(
            DetectorType.UNATTACHED_EBS_VOLUME,
            PersistenceState.PERSISTENT,
            Ownership(),
            [dependency],
        )
        == RemediationRisk.HIGH
    )
