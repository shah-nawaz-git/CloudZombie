from dataclasses import dataclass

from app.core.enums import ResourceType


@dataclass(frozen=True)
class DependencyCheckInfo:
    kind: str
    applies_to: ResourceType
    description: str
    blocks_remediation: bool


SUPPORTED_DEPENDENCY_CHECKS: tuple[DependencyCheckInfo, ...] = (
    DependencyCheckInfo(
        "ebs_attachment",
        ResourceType.EBS_VOLUME,
        "Checks whether an EBS volume is attached to an EC2 instance.",
        True,
    ),
    DependencyCheckInfo(
        "eip_association",
        ResourceType.ELASTIC_IP,
        "Checks whether an Elastic IP is associated with an instance or network interface.",
        True,
    ),
    DependencyCheckInfo(
        "attached_ebs_volume",
        ResourceType.EC2_INSTANCE,
        "Reports attached EBS volumes that continue to be billed for a stopped instance.",
        False,
    ),
    DependencyCheckInfo(
        "associated_elastic_ip",
        ResourceType.EC2_INSTANCE,
        "Reports public IPv4 addresses associated with a stopped instance.",
        False,
    ),
    DependencyCheckInfo(
        "registered_ami",
        ResourceType.EBS_SNAPSHOT,
        "Checks whether a snapshot is referenced by a registered AMI.",
        True,
    ),
    DependencyCheckInfo(
        "shared_snapshot",
        ResourceType.EBS_SNAPSHOT,
        "Checks whether a snapshot is shared with AWS accounts.",
        True,
    ),
    DependencyCheckInfo(
        "public_snapshot",
        ResourceType.EBS_SNAPSHOT,
        "Checks whether a snapshot is shared publicly.",
        True,
    ),
    DependencyCheckInfo(
        "snapshot_lock",
        ResourceType.EBS_SNAPSHOT,
        "Checks whether an EBS snapshot lock protects the snapshot.",
        True,
    ),
    DependencyCheckInfo(
        "aws_backup_managed",
        ResourceType.EBS_SNAPSHOT,
        "Checks whether snapshot metadata indicates AWS Backup management.",
        True,
    ),
)

__all__ = ["DependencyCheckInfo", "SUPPORTED_DEPENDENCY_CHECKS"]
