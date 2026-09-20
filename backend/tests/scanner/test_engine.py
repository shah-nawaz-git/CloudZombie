from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.enums import FindingStatus, PersistenceState, RemediationRisk, ScanStatus
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


def test_demo_scan_and_repeat_history(session_factory, fixed_clock, demo_dataset) -> None:
    engine = build_engine(session_factory, fixed_clock, demo_dataset)
    regions = ["eu-central-1", "us-east-1", "me-south-1"]
    first = engine.run_scan(regions)
    assert first.status == ScanStatus.COMPLETED
    assert first.account_id == "123456789012"
    assert first.completed_regions == ["eu-central-1", "us-east-1"]
    assert first.skipped_regions == ["me-south-1"]
    assert first.estimated_exposure == Decimal("105.5000")
    with session_factory() as session:
        findings = list(session.scalars(select(Finding)))
        assert {item.resource_id for item in findings if item.status == FindingStatus.OPEN} == {
            "vol-0a1b2c3d4e5f60001",
            "vol-0a1b2c3d4e5f60002",
            "vol-0a1b2c3d4e5f60003",
        }
        assert {item.resource_id for item in findings if item.status == FindingStatus.IGNORED} == {
            "vol-0a1b2c3d4e5f60004"
        }
        first_ids = {item.resource_id: item.id for item in findings}
        first_observed = {item.resource_id: item.first_observed_at for item in findings}

    fixed_clock.advance_to(fixed_clock.now() + timedelta(days=7))
    second = engine.run_scan(regions)
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


def test_requested_regions_are_respected(session_factory, fixed_clock, demo_dataset) -> None:
    scan = build_engine(session_factory, fixed_clock, demo_dataset).run_scan(["us-east-1"])
    assert scan.requested_regions == ["us-east-1"]
    assert set(scan.coverage) == {"us-east-1"}


def test_identity_credentials_failure_records_failed_scan(
    session_factory, fixed_clock, demo_dataset
) -> None:
    class FailingIdentityProvider(DemoProvider):
        def get_identity(self):
            raise ProviderCredentialsError("expired")

    provider = FailingIdentityProvider(demo_dataset, 5, fixed_clock.now())
    scan = build_engine(session_factory, fixed_clock, demo_dataset, provider).run_scan()
    assert scan.status == ScanStatus.FAILED
    assert scan.errors[0]["code"] == "credentials_error"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Finding)) == 0
        assert session.scalar(select(func.count()).select_from(Scan)) == 1
