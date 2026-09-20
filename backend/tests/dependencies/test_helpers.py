from datetime import UTC, datetime

from app.dependencies.ebs import attachment_dependencies
from app.dependencies.ec2 import stopped_instance_dependencies
from app.dependencies.eip import association_dependencies
from app.dependencies.snapshot import snapshot_dependencies
from app.providers.base import (
    Address,
    Attachment,
    Image,
    Instance,
    Snapshot,
    SnapshotAttributes,
    SnapshotLock,
)
from tests.conftest import make_volume


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


def test_ebs_attachment_present_is_blocking_and_none_is_empty() -> None:
    assert attachment_dependencies(make_volume()) == []
    volume = make_volume(attachments=(Attachment("i-0a1b2c3d4e5f60001", "/dev/sdf", "attached"),))
    dependencies = attachment_dependencies(volume)
    assert len(dependencies) == 1
    assert dependencies[0].kind == "ebs_attachment"
    assert dependencies[0].blocks_remediation is True


def test_eip_association_present_is_blocking_and_none_is_empty() -> None:
    assert association_dependencies(address()) == []
    dependencies = association_dependencies(
        address(instance_id="i-1", network_interface_id="eni-1")
    )
    assert len(dependencies) == 2
    assert {item.kind for item in dependencies} == {"eip_association"}
    assert all(item.blocks_remediation for item in dependencies)


def test_stopped_instance_dependency_counts() -> None:
    instance = Instance(
        "i-0a1b2c3d4e5f60001",
        "stopped",
        "t3.micro",
        datetime(2026, 1, 1, tzinfo=UTC),
        (),
        {},
        None,
    )
    dependencies = stopped_instance_dependencies(
        instance,
        [make_volume(), make_volume(volume_id="vol-0a1b2c3d4e5f60002")],
        [address(instance_id=instance.instance_id)],
    )
    assert [item.kind for item in dependencies] == [
        "attached_ebs_volume",
        "attached_ebs_volume",
        "associated_elastic_ip",
    ]
    assert not any(item.blocks_remediation for item in dependencies)


def test_snapshot_dependencies_cover_each_flag() -> None:
    snapshot = Snapshot(
        "snap-0a1b2c3d4e5f60001",
        None,
        "123456789012",
        "completed",
        datetime(2026, 1, 1, tzinfo=UTC),
        1,
        "standard",
        True,
        "backup",
        {},
    )
    dependencies = snapshot_dependencies(
        snapshot,
        [Image("ami-1", "image", "available", (snapshot.snapshot_id,), {})],
        SnapshotAttributes(snapshot.snapshot_id, ("210987654321",), ("all",)),
        SnapshotLock(snapshot.snapshot_id, "governance"),
        True,
    )
    assert {item.kind for item in dependencies} == {
        "registered_ami",
        "shared_snapshot",
        "public_snapshot",
        "snapshot_lock",
        "aws_backup_managed",
    }
    assert all(item.blocks_remediation for item in dependencies)
