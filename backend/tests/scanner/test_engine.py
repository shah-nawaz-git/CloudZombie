from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

import app.scanner.engine as engine_module
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
from app.providers.errors import ProviderCredentialsError
from app.scanner.engine import ScanEngine


def build_engine(session_factory, fixed_clock, demo_dataset, provider=None):
    settings = AppSettings(pricing_mode="fallback_only")
    selected = provider or DemoProvider(demo_dataset, step=5, anchor=fixed_clock.now())
    pricing = PricingService(selected, settings, fixed_clock)
    return ScanEngine(selected, session_factory, settings, pricing, fixed_clock)


def reload_scan(session_factory, scan_id):
    with session_factory() as session:
        return session.get(Scan, scan_id)


def test_demo_scan_and_repeat_history(session_factory, fixed_clock, demo_dataset) -> None:
    engine = build_engine(session_factory, fixed_clock, demo_dataset)
    regions = ["eu-central-1", "us-east-1", "me-south-1"]
    first_id = engine.run_scan(regions).id
    first = reload_scan(session_factory, first_id)
    assert first.status == ScanStatus.COMPLETED
    assert first.account_id == "123456789012"
    assert first.requested_regions == regions
    assert first.completed_regions == ["eu-central-1", "us-east-1"]
    assert first.skipped_regions == ["me-south-1"]
    assert set(first.coverage) == set(regions)
    with session_factory() as session:
        findings = list(session.scalars(select(Finding)))
        assert {item.resource_id for item in findings if item.status == FindingStatus.OPEN} >= {
            "vol-0a1b2c3d4e5f60001",
            "vol-0a1b2c3d4e5f60002",
            "vol-0a1b2c3d4e5f60003",
        }
        assert {item.resource_id for item in findings if item.status == FindingStatus.IGNORED} == {
            "vol-0a1b2c3d4e5f60004"
        }
        first_ids = {item.resource_id: item.id for item in findings}
        first_observed = {item.resource_id: item.first_observed_at for item in findings}
        expected_exposure = sum(
            (
                item.estimated_monthly_cost or Decimal("0")
                for item in findings
                if item.status == FindingStatus.OPEN and item.cost_confidence in {"HIGH", "MEDIUM"}
            ),
            Decimal("0"),
        )
    assert first.estimated_exposure == expected_exposure

    fixed_clock.advance_to(fixed_clock.now() + timedelta(days=7))
    second_id = engine.run_scan(regions).id
    second = reload_scan(session_factory, second_id)
    assert second.estimated_exposure == first.estimated_exposure
    with session_factory() as session:
        findings = list(session.scalars(select(Finding)))
        assert {item.resource_id: item.id for item in findings} == first_ids
        assert all(item.observation_count == 2 for item in findings)
        assert {item.resource_id: item.first_observed_at for item in findings} == first_observed
        assert all(item.last_observed_at == fixed_clock.now() for item in findings)
        hero = next(item for item in findings if item.resource_id.endswith("0001"))
        assert hero.persistence_state == PersistenceState.PERSISTENT
        assert hero.remediation_risk == RemediationRisk.LOW


def test_requested_regions_are_persisted(session_factory, fixed_clock, demo_dataset) -> None:
    scan_id = build_engine(session_factory, fixed_clock, demo_dataset).run_scan(["us-east-1"]).id
    scan = reload_scan(session_factory, scan_id)
    assert scan.requested_regions == ["us-east-1"]
    assert scan.completed_regions == ["us-east-1"]
    assert scan.skipped_regions == []
    assert set(scan.coverage) == {"us-east-1"}


def test_discovered_not_opted_in_region_is_visible(
    session_factory, fixed_clock, demo_dataset
) -> None:
    scan_id = build_engine(session_factory, fixed_clock, demo_dataset).run_scan().id
    scan = reload_scan(session_factory, scan_id)
    assert "me-south-1" in scan.requested_regions
    assert "me-south-1" in scan.skipped_regions
    assert scan.coverage["me-south-1"]["status"] == "skipped"
    assert scan.coverage["me-south-1"]["warnings"] == ["region not enabled (opt-in required)"]


def test_pricing_warnings_are_deduplicated_in_region_coverage(
    session_factory, fixed_clock, demo_dataset
) -> None:
    settings = AppSettings(pricing_mode="auto")
    provider = DemoProvider(demo_dataset, 5, fixed_clock.now())
    pricing = PricingService(provider, settings, fixed_clock)
    scan_id = (
        ScanEngine(provider, session_factory, settings, pricing, fixed_clock)
        .run_scan(["us-east-1"])
        .id
    )
    scan = reload_scan(session_factory, scan_id)
    warnings = scan.coverage["us-east-1"]["warnings"]
    assert len(warnings) == 1
    assert "ProviderTransientError" in warnings[0]


def test_unexpected_detector_error_marks_cell_failed(
    session_factory, fixed_clock, demo_dataset, monkeypatch
) -> None:
    class BrokenDetector:
        detector_type = DetectorType.UNATTACHED_EBS_VOLUME

        def scan(self, provider, region, context):
            raise RuntimeError("detector bug")

    monkeypatch.setattr(engine_module, "DETECTORS", [BrokenDetector()])
    scan_id = build_engine(session_factory, fixed_clock, demo_dataset).run_scan(["us-east-1"]).id
    scan = reload_scan(session_factory, scan_id)
    cell = scan.coverage["us-east-1"]["detectors"]["unattached_ebs_volume"]
    assert cell["status"] == "failed"
    assert cell["error_code"] == "internal_error"
    assert cell["message"] == "RuntimeError: detector bug"


def test_existing_running_scan_id_is_reused(session_factory, fixed_clock, demo_dataset) -> None:
    with session_factory() as session:
        existing = Scan(
            mode="demo",
            started_at=fixed_clock.now(),
            status="running",
            requested_regions=["us-east-1"],
            completed_regions=[],
            partial_regions=[],
            failed_regions=[],
            skipped_regions=[],
            coverage={},
            errors=[],
            created_at=fixed_clock.now(),
        )
        session.add(existing)
        session.commit()
        scan_id = existing.id
        started_at = existing.started_at
    result = build_engine(session_factory, fixed_clock, demo_dataset).run_scan(
        ["us-east-1"], scan_id=scan_id
    )
    assert result.id == scan_id
    assert result.started_at == started_at
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Scan)) == 1


def test_identity_credentials_failure_records_failed_scan(
    session_factory, fixed_clock, demo_dataset
) -> None:
    class FailingIdentityProvider(DemoProvider):
        def get_identity(self):
            raise ProviderCredentialsError("expired")

    provider = FailingIdentityProvider(demo_dataset, 5, fixed_clock.now())
    scan_id = build_engine(session_factory, fixed_clock, demo_dataset, provider).run_scan().id
    scan = reload_scan(session_factory, scan_id)
    assert scan.status == ScanStatus.FAILED
    assert scan.errors[0]["code"] == "credentials_error"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Finding)) == 0
        assert session.scalar(select(func.count()).select_from(Scan)) == 1
