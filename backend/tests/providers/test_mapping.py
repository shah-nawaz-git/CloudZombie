from datetime import UTC, datetime

import pytest

from app.providers.aws.mapping import (
    map_address,
    map_identity,
    map_image,
    map_instance,
    map_snapshot,
    map_volume,
)
from app.providers.errors import ProviderMalformedResponseError

NOW = datetime(2026, 9, 20, tzinfo=UTC)


def test_resource_mappings_accept_missing_optional_fields() -> None:
    volume = map_volume(
        {
            "VolumeId": "vol-1",
            "State": "available",
            "VolumeType": "gp3",
            "Size": 1,
            "CreateTime": NOW,
            "AvailabilityZone": "us-east-1a",
        }
    )
    assert volume.iops is None and volume.attachments == ()
    assert map_address({"PublicIp": "203.0.113.1"}).allocation_id is None
    instance = map_instance(
        {
            "InstanceId": "i-1",
            "State": {"Name": "running"},
            "InstanceType": "t3.micro",
            "LaunchTime": NOW,
        }
    )
    assert instance.block_devices == ()
    snapshot = map_snapshot(
        {
            "SnapshotId": "snap-1",
            "VolumeId": "vol-1",
            "OwnerId": "1",
            "State": "completed",
            "StartTime": NOW,
            "VolumeSize": 1,
        }
    )
    assert snapshot.storage_tier == "standard"
    image = map_image({"ImageId": "ami-1", "State": "available"})
    assert image.snapshot_ids == ()


def test_missing_required_field_is_malformed() -> None:
    with pytest.raises(ProviderMalformedResponseError):
        map_volume({"State": "available"})


@pytest.mark.parametrize(
    ("arn", "expected"),
    [
        ("arn:aws:iam::1:role/x", "role"),
        ("arn:aws:iam::1:user/x", "user"),
        ("arn:aws:sts::1:assumed-role/x/y", "assumed-role"),
        ("arn:aws:iam::1:root", "root"),
    ],
)
def test_identity_type_from_arn(arn, expected) -> None:
    identity = map_identity({"Account": "123456789012", "Arn": arn, "UserId": "x"})
    assert identity.identity_type == expected
