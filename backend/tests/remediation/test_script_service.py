from uuid import UUID

from app.core.clock import FixedClock
from app.core.enums import DetectorType, PersistenceState, RemediationRisk, ResourceType
from app.models import AppSettings
from app.services.script_service import ScriptService
from tests.remediation.finding_factory import NOW, make_finding


def test_bulk_includes_only_guarded_eligible_findings() -> None:
    eligible = make_finding()
    ineligible = make_finding(
        id=UUID("22222222-2222-4222-8222-222222222223"),
        persistence_state=PersistenceState.NEWLY_OBSERVED.value,
        remediation_risk=RemediationRisk.REVIEW.value,
    )
    result = ScriptService(AppSettings(), FixedClock(NOW)).bulk([eligible, ineligible])
    assert result.script is not None
    assert result.included == [eligible.id]
    assert result.skipped[0]["finding_id"] == str(ineligible.id)
    assert eligible.resource_id in result.script.content


def test_bulk_skips_eligible_finding_from_different_account() -> None:
    first = make_finding()
    second = make_finding(
        id=UUID("22222222-2222-4222-8222-222222222224"),
        account_id="210987654321",
        resource_id="vol-0a1b2c3d4e5f60002",
    )
    result = ScriptService(AppSettings(), FixedClock(NOW)).bulk([first, second])
    assert result.included == [first.id]
    assert result.skipped == [
        {
            "finding_id": str(second.id),
            "reason": "Finding belongs to a different AWS account than the first eligible finding.",
        }
    ]


def test_bulk_none_when_no_findings_are_eligible() -> None:
    stopped = make_finding(
        resource_type=ResourceType.EC2_INSTANCE.value,
        resource_id="i-0a1b2c3d4e5f60001",
        detector_type=DetectorType.STOPPED_EC2_INSTANCE.value,
        remediation_risk=RemediationRisk.REVIEW.value,
    )
    result = ScriptService(AppSettings(), FixedClock(NOW)).bulk([stopped])
    assert result.script is None
    assert result.included == []
    assert len(result.skipped) == 1
