from app.core.enums import DetectionConfidence, DetectorType, ResourceType
from app.dependencies.ebs import attachment_dependencies
from app.detectors.base import Detector, ScanContext
from app.detectors.ignore import evaluate_ignore
from app.models import EbsVolumePricingRequest, FindingCandidate
from app.providers.base import CloudProvider


class UnattachedEbsVolumeDetector(Detector):
    detector_type = DetectorType.UNATTACHED_EBS_VOLUME
    resource_type = ResourceType.EBS_VOLUME
    required_operations = frozenset({"ec2:DescribeVolumes"})

    def scan(
        self, provider: CloudProvider, region: str, context: ScanContext
    ) -> list[FindingCandidate]:
        candidates: list[FindingCandidate] = []
        for volume in provider.list_volumes(region):
            if volume.state != "available" or volume.attachments:
                continue
            ignore = evaluate_ignore(volume.tags, context.settings)
            evidence = {
                "volume_id": volume.volume_id,
                "availability_zone": volume.availability_zone,
                "state": volume.state,
                "volume_type": volume.volume_type,
                "size_gib": volume.size_gib,
                "iops": volume.iops,
                "throughput_mibps": volume.throughput_mibps,
                "encrypted": volume.encrypted,
                "created_at": volume.created_at.isoformat(),
                "origin_snapshot_id": volume.snapshot_id,
                "attachment_count": len(volume.attachments),
                "tags": dict(volume.tags),
                "name_tag": volume.tags.get("Name"),
            }
            candidates.append(
                FindingCandidate(
                    account_id=context.account_id,
                    region=region,
                    resource_type=self.resource_type,
                    resource_id=volume.volume_id,
                    detector_type=self.detector_type,
                    title=f"Unattached EBS volume {volume.volume_id}",
                    summary=(
                        f"This {volume.size_gib} GiB {volume.volume_type} volume is currently "
                        "in state 'available' with no attachments."
                    ),
                    resource_created_at=volume.created_at,
                    evidence=evidence,
                    known_dependencies=attachment_dependencies(volume),
                    tags=dict(volume.tags),
                    ignored=ignore.ignored,
                    ignore_reason=ignore.reason,
                    pricing_request=EbsVolumePricingRequest(
                        region=region,
                        volume_type=volume.volume_type,
                        size_gib=volume.size_gib,
                        iops=volume.iops,
                        throughput_mibps=volume.throughput_mibps,
                    ),
                    detection_confidence=DetectionConfidence.HIGH,
                )
            )
        return candidates
