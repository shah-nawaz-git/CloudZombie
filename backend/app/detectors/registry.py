from app.detectors.base import Detector
from app.detectors.ebs_unattached import UnattachedEbsVolumeDetector
from app.detectors.ec2_stopped import StoppedEc2InstanceDetector
from app.detectors.eip_unassociated import UnassociatedElasticIpDetector
from app.detectors.snapshot_missing_source import SnapshotMissingSourceVolumeDetector

DETECTORS: list[Detector] = [
    UnattachedEbsVolumeDetector(),
    UnassociatedElasticIpDetector(),
    StoppedEc2InstanceDetector(),
    SnapshotMissingSourceVolumeDetector(),
]
