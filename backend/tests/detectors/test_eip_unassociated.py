from app.detectors.base import ScanContext
from app.detectors.eip_unassociated import UnassociatedElasticIpDetector
from app.models import AppSettings, ElasticIpPricingRequest
from app.providers.base import Address


class Provider:
    def __init__(self, addresses):
        self.addresses = addresses

    def list_addresses(self, region):
        return self.addresses


def address(**changes):
    values = {
        "allocation_id": "eipalloc-0a1b2c3d4e5f60001",
        "public_ip": "203.0.113.1",
        "association_id": None,
        "instance_id": None,
        "network_interface_id": None,
        "domain": "vpc",
        "tags": {},
    }
    values.update(changes)
    return Address(**values)


def scan(selected, fixed_clock):
    context = ScanContext("123456789012", "us-east-1", fixed_clock.now(), AppSettings())
    return UnassociatedElasticIpDetector().scan(Provider([selected]), "us-east-1", context)


def test_unassociated_address_emits_candidate(fixed_clock) -> None:
    candidate = scan(address(), fixed_clock)[0]
    assert isinstance(candidate.pricing_request, ElasticIpPricingRequest)
    assert candidate.resource_created_at is None
    assert candidate.detection_confidence == "HIGH"


def test_associated_address_does_not_emit(fixed_clock) -> None:
    assert scan(address(association_id="eipassoc-1", instance_id="i-1"), fixed_clock) == []


def test_network_interface_only_association_does_not_emit(fixed_clock) -> None:
    assert scan(address(network_interface_id="eni-1"), fixed_clock) == []


def test_ignored_address_still_emits(fixed_clock) -> None:
    candidate = scan(
        address(tags={"cloudzombie:ignore": "TRUE", "cloudzombie:reason": "reserved"}),
        fixed_clock,
    )[0]
    assert candidate.ignored is True
    assert candidate.ignore_reason == "reserved"
