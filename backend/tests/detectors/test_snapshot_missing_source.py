from datetime import UTC, datetime

from app.detectors.base import ScanContext
from app.detectors.snapshot_missing_source import SnapshotMissingSourceVolumeDetector
from app.models import AppSettings
from app.providers.base import Image, Snapshot, SnapshotAttributes, SnapshotLock
from app.providers.errors import ProviderPermissionError
from tests.conftest import make_volume


class Provider:
    def __init__(
        self,
        snapshots,
        volumes=None,
        images=None,
        attributes=None,
        locks=None,
        attributes_error=False,
    ):
        self.snapshots = snapshots
        self.volumes = volumes or []
        self.images = images or []
        self.attributes = attributes or SnapshotAttributes(snapshots[0].snapshot_id, (), ())
        self.locks = locks or []
        self.attributes_error = attributes_error

    def list_snapshots(self, region):
        return self.snapshots

    def list_volumes(self, region):
        return self.volumes

    def list_images(self, region):
        return self.images

    def get_snapshot_attributes(self, region, snapshot_id):
        if self.attributes_error:
            raise ProviderPermissionError("ec2:DescribeSnapshotAttribute", region)
        return self.attributes

    def get_snapshot_locks(self, region, snapshot_ids):
        return self.locks


def snapshot(**changes):
    values = {
        "snapshot_id": "snap-0a1b2c3d4e5f60001",
        "volume_id": "vol-0deadbeef00000001",
        "owner_id": "123456789012",
        "state": "completed",
        "started_at": datetime(2026, 1, 1, tzinfo=UTC),
        "volume_size_gib": 100,
        "storage_tier": "standard",
        "encrypted": True,
        "description": "backup",
        "tags": {},
    }
    values.update(changes)
    return Snapshot(**values)


def scan(provider, fixed_clock):
    context = ScanContext("123456789012", "us-east-1", fixed_clock.now(), AppSettings())
    return SnapshotMissingSourceVolumeDetector().scan(provider, "us-east-1", context)


def test_source_exists_does_not_emit(fixed_clock) -> None:
    selected = snapshot()
    assert (
        scan(Provider([selected], [make_volume(volume_id=selected.volume_id)]), fixed_clock) == []
    )


def test_missing_source_emits_candidate(fixed_clock) -> None:
    candidate = scan(Provider([snapshot()]), fixed_clock)[0]
    assert candidate.evidence["source_volume_exists"] is False
    assert candidate.title.startswith("Snapshot with deleted source volume")


def test_placeholder_other_owner_and_pending_do_not_emit(fixed_clock) -> None:
    for selected in (
        snapshot(volume_id="vol-ffffffff"),
        snapshot(owner_id="210987654321"),
        snapshot(state="pending"),
    ):
        assert scan(Provider([selected]), fixed_clock) == []


def test_ami_reference_is_blocking(fixed_clock) -> None:
    selected = snapshot()
    image = Image("ami-0a1b2c3d4e5f60001", "image", "available", (selected.snapshot_id,), {})
    candidate = scan(Provider([selected], images=[image]), fixed_clock)[0]
    assert "registered_ami" in {item.kind for item in candidate.known_dependencies}


def test_shared_and_public_are_blocking(fixed_clock) -> None:
    selected = snapshot()
    attributes = SnapshotAttributes(selected.snapshot_id, ("210987654321",), ("all",))
    candidate = scan(Provider([selected], attributes=attributes), fixed_clock)[0]
    kinds = {item.kind for item in candidate.known_dependencies}
    assert {"shared_snapshot", "public_snapshot"} <= kinds


def test_lock_and_backup_are_blocking(fixed_clock) -> None:
    selected = snapshot(tags={"aws:backup:source-resource": "db"})
    lock = SnapshotLock(selected.snapshot_id, "governance")
    candidate = scan(Provider([selected], locks=[lock]), fixed_clock)[0]
    kinds = {item.kind for item in candidate.known_dependencies}
    assert {"snapshot_lock", "aws_backup_managed"} <= kinds


def test_attribute_permission_error_is_warning_and_unknown(fixed_clock) -> None:
    candidate = scan(Provider([snapshot()], attributes_error=True), fixed_clock)[0]
    assert candidate.evidence["shared_with_account_ids"] == "unknown"
    assert candidate.evidence["shared_publicly"] == "unknown"
    assert candidate.warnings == [
        "Snapshot sharing details unavailable: missing ec2:DescribeSnapshotAttribute"
    ]


def test_ignore_tag_still_emits(fixed_clock) -> None:
    candidate = scan(Provider([snapshot(tags={"cloudzombie:ignore": "true"})]), fixed_clock)[0]
    assert candidate.ignored is True
