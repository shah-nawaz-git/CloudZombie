from datetime import UTC, datetime

from app.detectors.base import ScanContext
from app.detectors.ec2_stopped import StoppedEc2InstanceDetector
from app.models import AppSettings, StoppedInstancePricingRequest
from app.providers.base import Address, BlockDevice, Instance
from app.providers.errors import ProviderPermissionError
from tests.conftest import make_volume


class Provider:
    def __init__(self, instances, volumes=None, addresses=None, volume_error=False):
        self.instances = instances
        self.volumes = volumes or []
        self.addresses = addresses or []
        self.volume_error = volume_error

    def list_instances(self, region):
        return self.instances

    def list_volumes(self, region):
        if self.volume_error:
            raise ProviderPermissionError("ec2:DescribeVolumes", region)
        return self.volumes

    def list_addresses(self, region):
        return self.addresses


def instance(state="stopped", devices=()):
    return Instance(
        instance_id="i-0a1b2c3d4e5f60001",
        state=state,
        instance_type="t3.large",
        launched_at=datetime(2026, 1, 1, tzinfo=UTC),
        block_devices=devices,
        tags={},
        platform=None,
    )


def context(fixed_clock):
    return ScanContext("123456789012", "us-east-1", fixed_clock.now(), AppSettings())


def test_running_instance_does_not_emit(fixed_clock) -> None:
    candidates = StoppedEc2InstanceDetector().scan(
        Provider([instance("running")]), "us-east-1", context(fixed_clock)
    )
    assert candidates == []


def test_stopped_instance_with_volumes_and_eip(fixed_clock) -> None:
    devices = (
        BlockDevice("/dev/xvda", "vol-0a1b2c3d4e5f60001", "attached"),
        BlockDevice("/dev/sdf", "vol-0a1b2c3d4e5f60002", "attached"),
    )
    volumes = [
        make_volume(volume_id=devices[0].volume_id, size_gib=80),
        make_volume(volume_id=devices[1].volume_id, size_gib=200, volume_type="gp2"),
    ]
    eip = Address(
        "eipalloc-0a1b2c3d4e5f60001",
        "203.0.113.1",
        "assoc",
        "i-0a1b2c3d4e5f60001",
        "eni-1",
        "vpc",
        {},
    )
    candidate = StoppedEc2InstanceDetector().scan(
        Provider([instance(devices=devices)], volumes, [eip]),
        "us-east-1",
        context(fixed_clock),
    )[0]
    assert [item.kind for item in candidate.known_dependencies] == [
        "attached_ebs_volume",
        "attached_ebs_volume",
        "associated_elastic_ip",
    ]
    assert set(candidate.related_resource_ids) == {
        devices[0].volume_id,
        devices[1].volume_id,
        eip.allocation_id,
    }
    assert isinstance(candidate.pricing_request, StoppedInstancePricingRequest)
    assert len(candidate.pricing_request.volumes) == 2
    assert candidate.pricing_request.public_ipv4_count == 1


def test_stopped_instance_without_residual_resources_still_emits(fixed_clock) -> None:
    candidate = StoppedEc2InstanceDetector().scan(
        Provider([instance()]), "us-east-1", context(fixed_clock)
    )[0]
    assert candidate.known_dependencies == []
    assert candidate.pricing_request.volumes == []
    assert candidate.pricing_request.public_ipv4_count == 0


def test_volume_permission_error_is_warning_not_cell_failure(fixed_clock) -> None:
    candidate = StoppedEc2InstanceDetector().scan(
        Provider([instance()], volume_error=True), "us-east-1", context(fixed_clock)
    )[0]
    assert candidate.warnings == [
        "Attached volume details unavailable: missing ec2:DescribeVolumes"
    ]
