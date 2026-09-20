from app.models import KnownDependency
from app.providers.base import Image, Snapshot, SnapshotAttributes, SnapshotLock


def snapshot_dependencies(
    snapshot: Snapshot,
    images: list[Image],
    attributes: SnapshotAttributes | None,
    lock: SnapshotLock | None,
    aws_backup: bool,
) -> list[KnownDependency]:
    dependencies = [
        KnownDependency(
            kind="registered_ami",
            target_id=image.image_id,
            description=f"Snapshot is referenced by registered AMI {image.image_id}.",
            blocks_remediation=True,
        )
        for image in images
    ]
    if attributes is not None and attributes.shared_user_ids:
        dependencies.append(
            KnownDependency(
                kind="shared_snapshot",
                description="Snapshot is shared with one or more AWS accounts.",
                blocks_remediation=True,
            )
        )
    if attributes is not None and "all" in attributes.shared_groups:
        dependencies.append(
            KnownDependency(
                kind="public_snapshot",
                description="Snapshot is shared publicly.",
                blocks_remediation=True,
            )
        )
    if lock is not None and lock.lock_state not in {None, "expired"}:
        dependencies.append(
            KnownDependency(
                kind="snapshot_lock",
                target_id=snapshot.snapshot_id,
                description=f"Snapshot lock state is {lock.lock_state}.",
                blocks_remediation=True,
            )
        )
    if aws_backup:
        dependencies.append(
            KnownDependency(
                kind="aws_backup_managed",
                target_id=snapshot.snapshot_id,
                description="Snapshot appears to be managed by AWS Backup.",
                blocks_remediation=True,
            )
        )
    return dependencies
