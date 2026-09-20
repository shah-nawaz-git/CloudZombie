from datetime import timedelta

from sqlalchemy import select

from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.enums import (
    DetectorType,
    FindingStatus,
    PersistenceState,
    RemediationRisk,
    ScanStatus,
)
from app.models import AppSettings
from app.persistence.models import Finding, Scan
from app.pricing.service import PricingService
from app.providers.demo import DemoProvider
from app.scanner.engine import ScanEngine
from app.services.demo_seeder import DemoSeeder


def run_step(session_factory, dataset, settings, anchor, step, observed_at):
    clock = FixedClock(observed_at)
    provider = DemoProvider(dataset, step, anchor)
    pricing = PricingService(provider, settings, clock)
    return ScanEngine(provider, session_factory, settings, pricing, clock).run_scan()


def ids(findings, detector, status=FindingStatus.OPEN):
    return {
        finding.resource_id
        for finding in findings
        if finding.detector_type == detector and finding.status == status
    }


def test_demo_timeline_evaluates_real_history(session_factory, fixed_clock, demo_dataset) -> None:
    anchor = fixed_clock.now()
    settings = AppSettings(pricing_mode="fallback_only")
    environment = Settings(CLOUDZOMBIE_MODE="demo")
    assert DemoSeeder(session_factory, environment, fixed_clock).seed_if_empty() is True
    assert DemoSeeder(session_factory, environment, fixed_clock).seed_if_empty() is False
    with session_factory() as session:
        scans = list(session.scalars(select(Scan).order_by(Scan.started_at)))
    assert len(scans) == 4
    assert all(scan.seeded for scan in scans)

    with session_factory() as session:
        findings = list(session.scalars(select(Finding)))
        scan4 = session.get(Scan, scans[-1].id)
        assert ids(findings, DetectorType.UNATTACHED_EBS_VOLUME) == {
            "vol-0a1b2c3d4e5f60001",
            "vol-0a1b2c3d4e5f60002",
            "vol-0a1b2c3d4e5f60003",
        }
        assert ids(findings, DetectorType.UNATTACHED_EBS_VOLUME, FindingStatus.IGNORED) == {
            "vol-0a1b2c3d4e5f60004"
        }
        assert ids(findings, DetectorType.UNATTACHED_EBS_VOLUME, FindingStatus.RESOLVED) == {
            "vol-0a1b2c3d4e5f60009"
        }
        assert ids(findings, DetectorType.UNASSOCIATED_ELASTIC_IP) == {
            "eipalloc-0a1b2c3d4e5f60001",
            "eipalloc-0a1b2c3d4e5f60002",
        }
        assert ids(findings, DetectorType.STOPPED_EC2_INSTANCE) == {
            "i-0a1b2c3d4e5f60001",
            "i-0a1b2c3d4e5f60002",
        }
        assert ids(findings, DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME) == {
            "snap-0a1b2c3d4e5f60001",
            "snap-0a1b2c3d4e5f60002",
            "snap-0a1b2c3d4e5f60003",
        }

        by_id = {finding.resource_id: finding for finding in findings}
        resolved = by_id["vol-0a1b2c3d4e5f60009"]
        assert resolved.resolved_at == anchor - timedelta(days=7)
        assert resolved.observation_count == 2
        assert resolved.first_observed_at == anchor - timedelta(days=21)

        hero = by_id["vol-0a1b2c3d4e5f60001"]
        assert hero.persistence_state == PersistenceState.PERSISTENT
        assert hero.remediation_risk == RemediationRisk.LOW
        assert hero.ownership["status"] == "UNKNOWN"
        assert hero.ownership["notes"] == [
            "Not found in any CloudFormation stack in eu-central-1. UNKNOWN does not mean "
            "unmanaged — Terraform, console or other tooling may own it."
        ]
        assert hero.first_observed_at == anchor - timedelta(days=21)
        assert hero.observation_count == hero.consecutive_observations == 4

        stack_volume = by_id["vol-0a1b2c3d4e5f60002"]
        assert stack_volume.ownership["status"] == "CONFIRMED"
        assert stack_volume.ownership["stack_name"] == "customer-api-prod"
        assert stack_volume.remediation_risk == RemediationRisk.HIGH

        retained_instance = by_id["i-0a1b2c3d4e5f60002"]
        assert retained_instance.ownership["status"] == "LIKELY"
        assert retained_instance.ownership["stack_name"] == "legacy-batch"
        assert retained_instance.remediation_risk == RemediationRisk.REVIEW

        new_volume = by_id["vol-0a1b2c3d4e5f60003"]
        assert new_volume.persistence_state == PersistenceState.NEWLY_OBSERVED
        assert new_volume.first_observed_at == anchor - timedelta(days=2)
        assert new_volume.observation_count == 1

        newer_eip = by_id["eipalloc-0a1b2c3d4e5f60002"]
        assert newer_eip.first_observed_at == anchor - timedelta(days=7)
        assert newer_eip.observation_count == 2
        assert newer_eip.persistence_state == PersistenceState.PERSISTENT

        assert by_id["snap-0a1b2c3d4e5f60002"].remediation_risk == RemediationRisk.HIGH
        assert by_id["snap-0a1b2c3d4e5f60003"].remediation_risk == RemediationRisk.HIGH
        assert by_id["snap-0a1b2c3d4e5f60001"].remediation_risk == RemediationRisk.REVIEW
        assert by_id["i-0a1b2c3d4e5f60002"].evidence["tags"]["Name"] == "$(rm -rf /)"

        snapshot_cell = scan4.coverage["ap-southeast-2"]["detectors"][
            DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME.value
        ]
        assert snapshot_cell["status"] == "missing_permission"
        assert snapshot_cell["missing_operation"] == "ec2:DescribeSnapshots"
        assert scan4.coverage["ap-southeast-2"]["status"] == "partial"
        assert scan4.coverage["me-south-1"]["status"] == "skipped"
        assert scan4.status == ScanStatus.PARTIAL
        assert len(findings) == 12

    scan5 = run_step(session_factory, demo_dataset, settings, anchor, 5, anchor)
    with session_factory() as session:
        hero = session.scalar(select(Finding).where(Finding.resource_id == "vol-0a1b2c3d4e5f60001"))
        reloaded_scan5 = session.get(Scan, scan5.id)
        assert hero.observation_count == 5
        assert hero.persistence_state == PersistenceState.PERSISTENT
        assert hero.first_observed_at == anchor - timedelta(days=21)
        assert reloaded_scan5.new_findings == 0
