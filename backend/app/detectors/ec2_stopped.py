from app.core.enums import DetectionConfidence, DetectorType, ResourceType
from app.dependencies.ec2 import stopped_instance_dependencies
from app.detectors.base import Detector, ScanContext
from app.detectors.ignore import evaluate_ignore
from app.models import EbsVolumePricingRequest, FindingCandidate, StoppedInstancePricingRequest
from app.providers.base import Address, CloudProvider, Volume
from app.providers.errors import ProviderPermissionError


class StoppedEc2InstanceDetector(Detector):
    detector_type = DetectorType.STOPPED_EC2_INSTANCE
    resource_type = ResourceType.EC2_INSTANCE
    required_operations = frozenset(
        {"ec2:DescribeInstances", "ec2:DescribeVolumes", "ec2:DescribeAddresses"}
    )

    def scan(
        self, provider: CloudProvider, region: str, context: ScanContext
    ) -> list[FindingCandidate]:
        instances = provider.list_instances(region)
        warnings: list[str] = []
        volumes: list[Volume] = []
        addresses: list[Address] = []
        try:
            volumes = provider.list_volumes(region)
        except ProviderPermissionError:
            warnings.append("Attached volume details unavailable: missing ec2:DescribeVolumes")
        try:
            addresses = provider.list_addresses(region)
        except ProviderPermissionError:
            warnings.append("Public IPv4 details unavailable: missing ec2:DescribeAddresses")
        volume_index = {volume.volume_id: volume for volume in volumes}
        candidates: list[FindingCandidate] = []
        for instance in instances:
            if instance.state != "stopped":
                continue
            attached = [
                volume_index[device.volume_id]
                for device in instance.block_devices
                if device.volume_id in volume_index
            ]
            associated = [
                address for address in addresses if address.instance_id == instance.instance_id
            ]
            attached_ids = [volume.volume_id for volume in attached]
            volume_details = [
                {
                    "volume_id": device.volume_id,
                    "device_name": device.device_name,
                    "volume_type": volume_index[device.volume_id].volume_type,
                    "size_gib": volume_index[device.volume_id].size_gib,
                    "iops": volume_index[device.volume_id].iops,
                    "throughput_mibps": volume_index[device.volume_id].throughput_mibps,
                }
                for device in instance.block_devices
                if device.volume_id in attached_ids
            ]
            storage_gib = sum(volume.size_gib for volume in attached)
            allocation_ids = [
                address.allocation_id for address in associated if address.allocation_id is not None
            ]
            ignore = evaluate_ignore(instance.tags, context.settings)
            related_ids = [*attached_ids, *allocation_ids]
            candidates.append(
                FindingCandidate(
                    account_id=context.account_id,
                    region=region,
                    resource_type=self.resource_type,
                    resource_id=instance.instance_id,
                    detector_type=self.detector_type,
                    title=f"Stopped EC2 instance {instance.instance_id}",
                    summary=(
                        "This instance is currently stopped. Stopped compute is not billed, "
                        f"but its {len(attached)} attached EBS volume(s) ({storage_gib} GiB) "
                        f"and {len(associated)} associated public IPv4 address(es) continue "
                        "to incur charges."
                    ),
                    resource_created_at=instance.launched_at,
                    evidence={
                        "instance_id": instance.instance_id,
                        "instance_type": instance.instance_type,
                        "state": instance.state,
                        "launched_at": instance.launched_at.isoformat(),
                        "launch_time_note": "LaunchTime is the last start time, not creation time.",
                        "platform": instance.platform,
                        "attached_volumes": volume_details,
                        "attached_storage_gib": storage_gib,
                        "associated_public_ipv4": allocation_ids,
                        "tags": dict(instance.tags),
                        "name_tag": instance.tags.get("Name"),
                    },
                    known_dependencies=stopped_instance_dependencies(
                        instance, attached, associated
                    ),
                    related_resource_ids=related_ids,
                    tags=dict(instance.tags),
                    ignored=ignore.ignored,
                    ignore_reason=ignore.reason,
                    pricing_request=StoppedInstancePricingRequest(
                        region=region,
                        volumes=[
                            EbsVolumePricingRequest(
                                region=region,
                                volume_type=volume.volume_type,
                                size_gib=volume.size_gib,
                                iops=volume.iops,
                                throughput_mibps=volume.throughput_mibps,
                            )
                            for volume in attached
                        ],
                        public_ipv4_count=len(associated),
                    ),
                    detection_confidence=DetectionConfidence.HIGH,
                    warnings=list(warnings),
                )
            )
        return candidates
