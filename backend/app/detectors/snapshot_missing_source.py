import re

from app.core.enums import DetectionConfidence, DetectorType, ResourceType
from app.dependencies.snapshot import snapshot_dependencies
from app.detectors.base import Detector, ScanContext
from app.detectors.ignore import evaluate_ignore
from app.models import FindingCandidate, SnapshotPricingRequest
from app.providers.base import (
    CloudProvider,
    Image,
    SnapshotAttributes,
    SnapshotLock,
)
from app.providers.errors import ProviderError

_VOLUME_ID = re.compile(r"^vol-[0-9a-f]{8}(?:[0-9a-f]{9})?$")
_PLACEHOLDER_VOLUME_ID = "vol-ffffffff"


class SnapshotMissingSourceVolumeDetector(Detector):
    detector_type = DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME
    resource_type = ResourceType.EBS_SNAPSHOT
    required_operations = frozenset({"ec2:DescribeSnapshots", "ec2:DescribeVolumes"})
    supplementary_operations = frozenset(
        {
            "ec2:DescribeImages",
            "ec2:DescribeSnapshotAttribute",
            "ec2:DescribeLockedSnapshots",
        }
    )

    def scan(
        self, provider: CloudProvider, region: str, context: ScanContext
    ) -> list[FindingCandidate]:
        snapshots = provider.list_snapshots(region)
        current_volume_ids = {volume.volume_id for volume in provider.list_volumes(region)}
        flagged = [
            snapshot
            for snapshot in snapshots
            if snapshot.owner_id == context.account_id
            and snapshot.state == "completed"
            and snapshot.volume_id != _PLACEHOLDER_VOLUME_ID
            and _VOLUME_ID.fullmatch(snapshot.volume_id)
            and snapshot.volume_id not in current_volume_ids
        ]
        if not flagged:
            return []
        image_warning: str | None = None
        images: list[Image] | None
        try:
            images = provider.list_images(region)
        except ProviderError:
            images = None
            image_warning = "AMI references unavailable: missing ec2:DescribeImages"
        lock_warning: str | None = None
        lock_index: dict[str, SnapshotLock] | None
        try:
            lock_index = {
                lock.snapshot_id: lock
                for lock in provider.get_snapshot_locks(
                    region, [snapshot.snapshot_id for snapshot in flagged]
                )
            }
        except ProviderError:
            lock_index = None
            lock_warning = "Snapshot lock details unavailable: missing ec2:DescribeLockedSnapshots"

        candidates: list[FindingCandidate] = []
        for snapshot in flagged:
            warnings = [warning for warning in (image_warning, lock_warning) if warning]
            references = (
                [image for image in images if snapshot.snapshot_id in image.snapshot_ids]
                if images is not None
                else []
            )
            attributes: SnapshotAttributes | None
            attribute_evidence: SnapshotAttributes | None | str
            try:
                attributes = provider.get_snapshot_attributes(region, snapshot.snapshot_id)
                attribute_evidence = attributes
            except ProviderError:
                attributes = None
                attribute_evidence = "unknown"
                warnings.append(
                    "Snapshot sharing details unavailable: missing ec2:DescribeSnapshotAttribute"
                )
            lock = lock_index.get(snapshot.snapshot_id) if lock_index is not None else None
            backup_managed = any(
                key.startswith("aws:backup:") for key in snapshot.tags
            ) or snapshot.description.startswith(
                "This snapshot is created by the AWS Backup service"
            )
            ignore = evaluate_ignore(snapshot.tags, context.settings)
            candidates.append(
                FindingCandidate(
                    account_id=context.account_id,
                    region=region,
                    resource_type=self.resource_type,
                    resource_id=snapshot.snapshot_id,
                    detector_type=self.detector_type,
                    title=f"Snapshot with deleted source volume {snapshot.snapshot_id}",
                    summary=(
                        f"This snapshot references source volume {snapshot.volume_id}, which "
                        f"no longer exists in {region}. That does not make the snapshot "
                        "unnecessary: it may back an AMI, be shared, or be part of a backup "
                        "plan. It deserves review."
                    ),
                    resource_created_at=snapshot.started_at,
                    evidence={
                        "snapshot_id": snapshot.snapshot_id,
                        "source_volume_id": snapshot.volume_id,
                        "state": snapshot.state,
                        "started_at": snapshot.started_at.isoformat(),
                        "volume_size_gib": snapshot.volume_size_gib,
                        "storage_tier": snapshot.storage_tier,
                        "encrypted": snapshot.encrypted,
                        "description": snapshot.description,
                        "tags": dict(snapshot.tags),
                        "name_tag": snapshot.tags.get("Name"),
                        "ami_references": (
                            [image.image_id for image in references]
                            if images is not None
                            else "unknown"
                        ),
                        "shared_with_account_ids": (
                            list(attribute_evidence.shared_user_ids)
                            if isinstance(attribute_evidence, SnapshotAttributes)
                            else "unknown"
                        ),
                        "shared_publicly": (
                            "all" in attribute_evidence.shared_groups
                            if isinstance(attribute_evidence, SnapshotAttributes)
                            else "unknown"
                        ),
                        "lock_state": (
                            lock.lock_state
                            if lock_index is not None and lock is not None
                            else None
                            if lock_index is not None
                            else "unknown"
                        ),
                        "aws_backup_managed": backup_managed,
                        "source_volume_exists": False,
                    },
                    known_dependencies=snapshot_dependencies(
                        snapshot, references, attributes, lock, backup_managed
                    ),
                    related_resource_ids=[
                        snapshot.volume_id,
                        *(image.image_id for image in references),
                    ],
                    tags=dict(snapshot.tags),
                    ignored=ignore.ignored,
                    ignore_reason=ignore.reason,
                    pricing_request=SnapshotPricingRequest(
                        region=region,
                        size_gib=snapshot.volume_size_gib,
                        storage_tier=snapshot.storage_tier,
                    ),
                    detection_confidence=DetectionConfidence.HIGH,
                    warnings=warnings,
                )
            )
        return candidates
