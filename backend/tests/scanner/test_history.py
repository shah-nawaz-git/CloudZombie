from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.enums import (
    DetectorCoverageStatus,
    DetectorType,
    FindingStatus,
    PersistenceState,
    ResourceType,
)
from app.models import AppSettings, FindingCandidate
from app.persistence.models import Finding, FindingObservation, Scan
from app.scanner.history import reconcile

ACCOUNT = "123456789012"
START = datetime(2026, 9, 1, tzinfo=UTC)


def make_scan(session, at=START):
    scan = Scan(
        mode="demo",
        account_id=ACCOUNT,
        principal_arn="arn",
        seeded=False,
        started_at=at,
        status="running",
        requested_regions=["us-east-1"],
        completed_regions=[],
        partial_regions=[],
        failed_regions=[],
        skipped_regions=[],
        coverage={},
        errors=[],
        created_at=at,
    )
    session.add(scan)
    session.flush()
    return scan


def candidate(
    region="us-east-1", resource_id="vol-0a1b2c3d4e5f60001", ignored=False, created_at=None
):
    return FindingCandidate(
        account_id=ACCOUNT,
        region=region,
        resource_type=ResourceType.EBS_VOLUME,
        resource_id=resource_id,
        detector_type=DetectorType.UNATTACHED_EBS_VOLUME,
        title=f"Unattached EBS volume {resource_id}",
        summary="This 1 GiB gp3 volume is currently in state 'available' with no attachments.",
        resource_created_at=created_at or START - timedelta(days=400),
        evidence={"version": 1},
        ignored=ignored,
        ignore_reason="policy" if ignored else None,
    )


def observe(session, at, candidates, status=DetectorCoverageStatus.COMPLETE, region="us-east-1"):
    scan = make_scan(session, at)
    result = reconcile(
        session,
        scan,
        region,
        DetectorType.UNATTACHED_EBS_VOLUME,
        candidates,
        status,
        AppSettings(),
        at,
    )
    session.commit()
    return scan, result


def finding(session, resource_id="vol-0a1b2c3d4e5f60001", region="us-east-1"):
    return session.scalar(
        select(Finding).where(Finding.resource_id == resource_id, Finding.region == region)
    )


def test_new_finding_fields_and_observation(session_factory) -> None:
    with session_factory() as session:
        scan, result = observe(session, START, [candidate()])
        row = finding(session)
        assert result.new == 1
        assert row.first_observed_at == row.last_observed_at == row.streak_started_at == START
        assert row.observation_count == row.consecutive_observations == 1
        assert row.status == FindingStatus.OPEN
        assert row.first_scan_id == row.last_scan_id == scan.id
        assert session.scalar(select(func.count()).select_from(FindingObservation)) == 1


def test_repeat_persistence_threshold(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate()])
        first = finding(session).first_observed_at
        observe(session, START + timedelta(days=6), [candidate()])
        row = finding(session)
        assert row.persistence_state == PersistenceState.NEWLY_OBSERVED
        observe(session, START + timedelta(days=7), [candidate()])
        row = finding(session)
        assert row.first_observed_at == first
        assert row.last_observed_at == START + timedelta(days=7)
        assert row.observation_count == row.consecutive_observations == 3
        assert row.persistence_state == PersistenceState.PERSISTENT


def test_resource_age_is_not_condition_age(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate(created_at=START - timedelta(days=400))])
        row = finding(session)
        assert row.persistence_state == PersistenceState.NEWLY_OBSERVED
        assert (row.last_observed_at - row.streak_started_at).days == 0
        combined = f"{row} {row.summary}".lower()
        assert not ("400 days" in combined and "unattached for" in combined)


def test_complete_absence_resolves_but_incomplete_coverage_does_not(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate()])
        observe(session, START + timedelta(days=1), [], DetectorCoverageStatus.MISSING_PERMISSION)
        row = finding(session)
        assert row.status == FindingStatus.OPEN
        observe(session, START + timedelta(days=2), [], DetectorCoverageStatus.FAILED)
        observe(session, START + timedelta(days=3), [], DetectorCoverageStatus.SKIPPED)
        assert finding(session).status == FindingStatus.OPEN
        observe(session, START + timedelta(days=4), [])
        row = finding(session)
        assert row.status == FindingStatus.RESOLVED
        assert row.resolved_at == START + timedelta(days=4)
        assert row.consecutive_observations == 0
        assert row.observation_count == 1 and row.first_observed_at == START


def test_reappearance_starts_new_streak_preserving_first(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate()])
        observe(session, START + timedelta(days=1), [])
        observe(session, START + timedelta(days=2), [candidate()])
        row = finding(session)
        assert row.status == FindingStatus.OPEN
        assert row.first_observed_at == START
        assert row.streak_started_at == START + timedelta(days=2)
        assert row.consecutive_observations == 1
        assert row.observation_count == 2
        assert row.resolved_at is None


def test_dismissed_reobservation_and_absence(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate()])
        row = finding(session)
        row.status = FindingStatus.DISMISSED
        session.commit()
        observe(session, START + timedelta(days=1), [candidate()])
        assert finding(session).status == FindingStatus.DISMISSED
        assert finding(session).observation_count == 2
        observe(session, START + timedelta(days=2), [])
        assert finding(session).status == FindingStatus.RESOLVED


def test_ignored_tag_transitions(session_factory) -> None:
    with session_factory() as session:
        observe(session, START, [candidate(ignored=True)])
        assert finding(session).status == FindingStatus.IGNORED
        observe(session, START + timedelta(days=1), [candidate(ignored=False)])
        assert finding(session).status == FindingStatus.OPEN
        observe(session, START + timedelta(days=2), [candidate(ignored=True)])
        observe(session, START + timedelta(days=3), [])
        assert finding(session).status == FindingStatus.RESOLVED


def test_other_regions_untouched_and_identity_includes_region(session_factory) -> None:
    with session_factory() as session:
        east = candidate(region="us-east-1")
        eu = candidate(region="eu-central-1")
        observe(session, START, [east])
        observe(session, START, [eu], region="eu-central-1")
        observe(session, START + timedelta(days=1), [], region="us-east-1")
        assert finding(session, region="us-east-1").status == FindingStatus.RESOLVED
        assert finding(session, region="eu-central-1").status == FindingStatus.OPEN
        assert session.scalar(select(func.count()).select_from(Finding)) == 2


def test_evidence_and_resource_created_at_refresh(session_factory) -> None:
    with session_factory() as session:
        original = candidate(created_at=START - timedelta(days=10))
        observe(session, START, [original])
        updated = original.model_copy(
            update={"evidence": {"version": 2}, "resource_created_at": START - timedelta(days=20)}
        )
        observe(session, START + timedelta(days=1), [updated])
        row = finding(session)
        assert row.evidence == {"version": 2}
        assert row.resource_created_at == START - timedelta(days=20)
        assert session.scalar(select(func.count()).select_from(FindingObservation)) == 2
