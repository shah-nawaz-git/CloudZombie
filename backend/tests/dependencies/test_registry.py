from datetime import UTC, datetime

from app.dependencies import SUPPORTED_DEPENDENCY_CHECKS
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


def test_registry_has_exact_supported_checks() -> None:
    assert {item.kind for item in SUPPORTED_DEPENDENCY_CHECKS} == {
        "ebs_attachment",
        "eip_association",
        "attached_ebs_volume",
        "associated_elastic_ip",
        "registered_ami",
        "shared_snapshot",
        "public_snapshot",
        "snapshot_lock",
        "aws_backup_managed",
    }


def test_every_helper_emitted_kind_is_registered() -> None:
    volume = make_volume(attachments=(Attachment("i-1", "/dev/sdf", "attached"),))
    address = Address("eipalloc-1", "203.0.113.1", "assoc", "i-1", "eni-1", "vpc", {})
    instance = Instance(
        "i-1", "stopped", "t3.micro", datetime(2026, 1, 1, tzinfo=UTC), (), {}, None
    )
    snapshot = Snapshot(
        "snap-1",
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
    emitted = {
        *(item.kind for item in attachment_dependencies(volume)),
        *(item.kind for item in association_dependencies(address)),
        *(item.kind for item in stopped_instance_dependencies(instance, [volume], [address])),
        *(
            item.kind
            for item in snapshot_dependencies(
                snapshot,
                [Image("ami-1", "image", "available", ("snap-1",), {})],
                SnapshotAttributes("snap-1", ("2",), ("all",)),
                SnapshotLock("snap-1", "governance"),
                True,
            )
        ),
    }
    registered = {item.kind for item in SUPPORTED_DEPENDENCY_CHECKS}
    assert emitted == registered
