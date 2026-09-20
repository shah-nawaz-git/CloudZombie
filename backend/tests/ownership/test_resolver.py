from sqlalchemy import select

from app.core.enums import DetectorType, OwnershipStatus, ResourceType
from app.models import AppSettings, FindingCandidate
from app.ownership.resolver import OwnershipResolver
from app.persistence.models import Finding
from app.pricing.service import PricingService
from app.providers.base import StackResource
from app.providers.demo import DemoProvider
from app.providers.errors import ProviderPermissionError, ProviderTransientError
from app.scanner.engine import ScanEngine


class Provider:
    def __init__(self, resources=None, error=None):
        self.resources = resources or []
        self.error = error
        self.calls = 0

    def list_stack_resources(self, region):
        self.calls += 1
        if self.error:
            raise self.error
        return self.resources


def candidate(resource_id="vol-0a1b2c3d4e5f60001", tags=None):
    return FindingCandidate(
        account_id="123456789012",
        region="us-east-1",
        resource_type=ResourceType.EBS_VOLUME,
        resource_id=resource_id,
        detector_type=DetectorType.UNATTACHED_EBS_VOLUME,
        title="volume",
        summary="volume",
        evidence={},
        tags=tags or {},
    )


def stack_resource():
    return StackResource(
        region="us-east-1",
        stack_name="customer-api-prod",
        stack_id="arn:stack",
        logical_id="DataVolume",
        physical_id="vol-0a1b2c3d4e5f60001",
        resource_type="AWS::EC2::Volume",
        resource_status="CREATE_COMPLETE",
    )


def test_confirmed_from_stack_resource_index() -> None:
    ownership = OwnershipResolver(Provider([stack_resource()]), "us-east-1").resolve(candidate())
    assert ownership.status == OwnershipStatus.CONFIRMED
    assert ownership.source == "stack_resource_index"
    assert ownership.stack_name == "customer-api-prod"
    assert ownership.logical_id == "DataVolume"
    assert ownership.notes == [
        "Found as logical resource DataVolume in stack customer-api-prod.",
        "Change the CloudFormation stack instead of deleting the resource manually.",
    ]


def test_likely_from_tags_when_index_available() -> None:
    ownership = OwnershipResolver(Provider(), "us-east-1").resolve(
        candidate(
            tags={
                "aws:cloudformation:stack-name": "retained-stack",
                "aws:cloudformation:logical-id": "DataVolume",
            }
        )
    )
    assert ownership.status == OwnershipStatus.LIKELY
    assert ownership.source == "tags"
    assert ownership.stack_name == "retained-stack"
    assert "retained resource" in ownership.notes[0]


def test_unknown_when_index_available() -> None:
    ownership = OwnershipResolver(Provider(), "us-east-1").resolve(candidate())
    assert ownership.status == OwnershipStatus.UNKNOWN
    assert ownership.notes == [
        "Not found in any CloudFormation stack in us-east-1. UNKNOWN does not mean "
        "unmanaged — Terraform, console or other tooling may own it."
    ]


def test_permission_failure_warning_and_tag_fallback() -> None:
    provider = Provider(error=ProviderPermissionError("cloudformation:ListStacks", "us-east-1"))
    resolver = OwnershipResolver(provider, "us-east-1")
    ownership = resolver.resolve(
        candidate(tags={"aws:cloudformation:stack-name": "retained-stack"})
    )
    assert ownership.status == OwnershipStatus.LIKELY
    assert ownership.notes == [
        "Resource carries aws:cloudformation:* tags; the stack index could not be queried."
    ]
    assert resolver.warning == (
        "CloudFormation ownership not evaluated in us-east-1: missing cloudformation:ListStacks"
    )


def test_provider_failure_unknown_reason() -> None:
    resolver = OwnershipResolver(
        Provider(error=ProviderTransientError("temporary outage")), "us-east-1"
    )
    ownership = resolver.resolve(candidate())
    assert ownership.status == OwnershipStatus.UNKNOWN
    assert ownership.notes == [
        "CloudFormation ownership could not be evaluated: temporary outage. UNKNOWN does "
        "not mean unmanaged."
    ]
    assert resolver.warning == "CloudFormation lookup failed in us-east-1: temporary outage"


def test_index_is_built_once_for_many_resolves() -> None:
    provider = Provider([stack_resource()])
    resolver = OwnershipResolver(provider, "us-east-1")
    resolver.resolve(candidate())
    resolver.resolve(candidate(resource_id="vol-0a1b2c3d4e5f60002"))
    assert provider.calls == 1


def test_engine_surfaces_ownership_warning(session_factory, fixed_clock, demo_dataset) -> None:
    class MissingCloudFormationProvider(DemoProvider):
        def list_stack_resources(self, region):
            raise ProviderPermissionError("cloudformation:ListStacks", region)

    settings = AppSettings(pricing_mode="fallback_only")
    provider = MissingCloudFormationProvider(demo_dataset, 5, fixed_clock.now())
    pricing = PricingService(provider, settings, fixed_clock)
    scan = ScanEngine(provider, session_factory, settings, pricing, fixed_clock).run_scan(
        ["us-east-1"]
    )
    with session_factory() as session:
        reloaded = session.get(type(scan), scan.id)
    assert reloaded.coverage["us-east-1"]["warnings"] == [
        "CloudFormation ownership not evaluated in us-east-1: missing cloudformation:ListStacks"
    ]


def test_engine_resolves_demo_ownership(session_factory, fixed_clock, demo_dataset) -> None:
    settings = AppSettings(pricing_mode="fallback_only")
    provider = DemoProvider(demo_dataset, 5, fixed_clock.now())
    pricing = PricingService(provider, settings, fixed_clock)
    ScanEngine(provider, session_factory, settings, pricing, fixed_clock).run_scan(
        ["eu-central-1", "us-east-1"]
    )
    with session_factory() as session:
        findings = {item.resource_id: item for item in session.scalars(select(Finding))}
    confirmed = findings["vol-0a1b2c3d4e5f60002"]
    likely = findings["i-0a1b2c3d4e5f60002"]
    assert confirmed.ownership["status"] == "CONFIRMED"
    assert confirmed.remediation_risk == "HIGH"
    assert likely.ownership["status"] == "LIKELY"
    assert likely.remediation_risk == "REVIEW"
