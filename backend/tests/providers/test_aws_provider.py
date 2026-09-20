import json

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import select

from app.core.enums import DetectorType, ScanStatus
from app.models import AppSettings
from app.persistence.models import Finding, Scan
from app.pricing.service import PricingService
from app.providers.aws.provider import AwsProvider
from app.providers.errors import (
    OperationNotAllowedError,
    ProviderPermissionError,
    ProviderRegionUnavailableError,
    ProviderThrottledError,
)
from app.scanner.engine import ScanEngine


def live_provider() -> AwsProvider:
    return AwsProvider(session=boto3.Session(region_name="us-east-1"), sleep=lambda _: None)


def create_instance(ec2, *, state="running"):
    instance = ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        Placement={"AvailabilityZone": "us-east-1a"},
    )["Instances"][0]
    if state == "stopped":
        ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
    return instance


@mock_aws
def test_identity_and_regions(aws_credentials) -> None:
    provider = live_provider()
    identity = provider.get_identity()
    assert identity.account_id == "123456789012"
    assert identity.principal_arn
    regions = provider.list_regions()
    assert any(region.name == "us-east-1" for region in regions)
    assert all(
        region.opt_in_status in {"opt-in-not-required", "opted-in", "not-opted-in"}
        for region in regions
    )


@mock_aws
def test_ec2_resource_mapping(aws_credentials) -> None:
    ec2 = boto3.client("ec2", region_name="us-east-1")
    available = ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=10,
        VolumeType="gp3",
        TagSpecifications=[
            {"ResourceType": "volume", "Tags": [{"Key": "Name", "Value": "available"}]}
        ],
    )["VolumeId"]
    attached = ec2.create_volume(AvailabilityZone="us-east-1a", Size=8, VolumeType="gp2")[
        "VolumeId"
    ]
    instance = create_instance(ec2)
    ec2.attach_volume(VolumeId=attached, InstanceId=instance["InstanceId"], Device="/dev/sdf")
    idle = ec2.allocate_address(Domain="vpc")["AllocationId"]
    associated = ec2.allocate_address(Domain="vpc")["AllocationId"]
    ec2.associate_address(AllocationId=associated, InstanceId=instance["InstanceId"])
    stopped = create_instance(ec2, state="stopped")

    provider = live_provider()
    volumes = {volume.volume_id: volume for volume in provider.list_volumes("us-east-1")}
    assert volumes[available].state == "available"
    assert volumes[available].tags["Name"] == "available"
    assert volumes[attached].attachments[0].instance_id == instance["InstanceId"]
    addresses = {address.allocation_id: address for address in provider.list_addresses("us-east-1")}
    assert addresses[idle].association_id is None
    assert addresses[associated].instance_id == instance["InstanceId"]
    instances = {item.instance_id: item for item in provider.list_instances("us-east-1")}
    assert instances[instance["InstanceId"]].state == "running"
    assert instances[stopped["InstanceId"]].state == "stopped"
    assert any(
        device.volume_id == attached for device in instances[instance["InstanceId"]].block_devices
    )


@mock_aws
def test_snapshots_images_and_attributes(aws_credentials) -> None:
    ec2 = boto3.client("ec2", region_name="us-east-1")
    volume_id = ec2.create_volume(AvailabilityZone="us-east-1a", Size=5)["VolumeId"]
    snapshot_id = ec2.create_snapshot(VolumeId=volume_id)["SnapshotId"]
    ec2.modify_snapshot_attribute(
        SnapshotId=snapshot_id,
        Attribute="createVolumePermission",
        OperationType="add",
        UserIds=["210987654321"],
    )
    image_id = ec2.register_image(
        Name="snapshot-image",
        RootDeviceName="/dev/sda1",
        BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {"SnapshotId": snapshot_id}}],
    )["ImageId"]
    ec2.delete_volume(VolumeId=volume_id)

    provider = live_provider()
    snapshots = {item.snapshot_id: item for item in provider.list_snapshots("us-east-1")}
    assert snapshots[snapshot_id].volume_id == volume_id
    images = {item.image_id: item for item in provider.list_images("us-east-1")}
    assert len(images[image_id].snapshot_ids) == 1
    assert images[image_id].snapshot_ids[0] in snapshots
    attributes = provider.get_snapshot_attributes("us-east-1", snapshot_id)
    assert attributes.shared_user_ids == ("210987654321",)


@mock_aws
def test_cloudformation_stack_resources(aws_credentials) -> None:
    cloudformation = boto3.client("cloudformation", region_name="us-east-1")
    template = {
        "Resources": {
            "DataVolume": {
                "Type": "AWS::EC2::Volume",
                "Properties": {"AvailabilityZone": "us-east-1a", "Size": 1},
            }
        }
    }
    cloudformation.create_stack(StackName="customer-api-prod", TemplateBody=json.dumps(template))
    resources = live_provider().list_stack_resources("us-east-1")
    volume = next(item for item in resources if item.logical_id == "DataVolume")
    assert volume.stack_name == "customer-api-prod"
    assert volume.physical_id.startswith("vol-")


@mock_aws
def test_full_scan_engine_with_live_provider(aws_credentials, session_factory, fixed_clock) -> None:
    ec2 = boto3.client("ec2", region_name="us-east-1")
    available = ec2.create_volume(AvailabilityZone="us-east-1a", Size=10, VolumeType="gp3")[
        "VolumeId"
    ]
    idle_eip = ec2.allocate_address(Domain="vpc")["AllocationId"]
    stopped = create_instance(ec2, state="stopped")["InstanceId"]
    source = ec2.create_volume(AvailabilityZone="us-east-1a", Size=5)["VolumeId"]
    snapshot = ec2.create_snapshot(VolumeId=source)["SnapshotId"]
    ec2.delete_volume(VolumeId=source)

    provider = live_provider()
    settings = AppSettings(pricing_mode="fallback_only")
    pricing = PricingService(provider, settings, fixed_clock)
    scan_id = (
        ScanEngine(provider, session_factory, settings, pricing, fixed_clock)
        .run_scan(["us-east-1", "eu-west-1"])
        .id
    )
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        findings = list(session.scalars(select(Finding)))
    assert scan.status == ScanStatus.COMPLETED
    assert {finding.resource_id for finding in findings} >= {
        available,
        idle_eip,
        stopped,
        snapshot,
    }


@pytest.mark.parametrize(
    ("method", "error", "expected_region_status", "expected_cell_status"),
    [
        (
            "describe_snapshots",
            ProviderPermissionError("ec2:DescribeSnapshots", "us-east-1"),
            "partial",
            "missing_permission",
        ),
        (
            "describe_volumes",
            ProviderRegionUnavailableError("us-east-1"),
            "skipped",
            "skipped",
        ),
        (
            "describe_volumes",
            ProviderThrottledError("throttled after four attempts"),
            "partial",
            "failed",
        ),
    ],
)
@mock_aws
def test_scan_provider_error_coverage(
    aws_credentials,
    session_factory,
    fixed_clock,
    monkeypatch,
    method,
    error,
    expected_region_status,
    expected_cell_status,
) -> None:
    provider = live_provider()
    wrapper = provider._AwsProvider__ec2("us-east-1")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(wrapper, method, fail)
    settings = AppSettings(pricing_mode="fallback_only")
    pricing = PricingService(provider, settings, fixed_clock)
    scan_id = (
        ScanEngine(provider, session_factory, settings, pricing, fixed_clock)
        .run_scan(["us-east-1"])
        .id
    )
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
    assert scan.coverage["us-east-1"]["status"] == expected_region_status
    detector = (
        DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME.value
        if method == "describe_snapshots"
        else DetectorType.UNATTACHED_EBS_VOLUME.value
    )
    assert scan.coverage["us-east-1"]["detectors"][detector]["status"] == expected_cell_status
    if isinstance(error, ProviderThrottledError):
        assert "throttled after four attempts" in scan.errors[0]["message"]


@mock_aws
def test_real_session_guard_blocks_mutation(aws_credentials) -> None:
    provider = live_provider()
    session = provider._AwsProvider__session
    with pytest.raises(OperationNotAllowedError):
        session.client("ec2", region_name="us-east-1").delete_volume(VolumeId="vol-1")
