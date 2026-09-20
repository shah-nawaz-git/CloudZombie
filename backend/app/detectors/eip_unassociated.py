from app.core.enums import DetectionConfidence, DetectorType, ResourceType
from app.dependencies.eip import association_dependencies
from app.detectors.base import Detector, ScanContext
from app.detectors.ignore import evaluate_ignore
from app.models import ElasticIpPricingRequest, FindingCandidate
from app.providers.base import CloudProvider


class UnassociatedElasticIpDetector(Detector):
    detector_type = DetectorType.UNASSOCIATED_ELASTIC_IP
    resource_type = ResourceType.ELASTIC_IP
    required_operations = frozenset({"ec2:DescribeAddresses"})

    def scan(
        self, provider: CloudProvider, region: str, context: ScanContext
    ) -> list[FindingCandidate]:
        candidates: list[FindingCandidate] = []
        for address in provider.list_addresses(region):
            if (
                address.allocation_id is None
                or address.association_id is not None
                or address.instance_id is not None
                or address.network_interface_id is not None
            ):
                continue
            ignore = evaluate_ignore(address.tags, context.settings)
            candidates.append(
                FindingCandidate(
                    account_id=context.account_id,
                    region=region,
                    resource_type=self.resource_type,
                    resource_id=address.allocation_id,
                    detector_type=self.detector_type,
                    title=f"Unassociated Elastic IP {address.allocation_id}",
                    summary=(
                        f"This Elastic IP address (allocation {address.allocation_id}) is "
                        "currently not associated with any instance or network interface. "
                        "AWS charges for public IPv4 addresses whether or not they are in use."
                    ),
                    resource_created_at=None,
                    evidence={
                        "allocation_id": address.allocation_id,
                        "public_ip": address.public_ip,
                        "domain": address.domain,
                        "association_id": address.association_id,
                        "instance_id": address.instance_id,
                        "network_interface_id": address.network_interface_id,
                        "tags": dict(address.tags),
                        "name_tag": address.tags.get("Name"),
                    },
                    known_dependencies=association_dependencies(address),
                    tags=dict(address.tags),
                    ignored=ignore.ignored,
                    ignore_reason=ignore.reason,
                    pricing_request=ElasticIpPricingRequest(region=region),
                    detection_confidence=DetectionConfidence.HIGH,
                )
            )
        return candidates
