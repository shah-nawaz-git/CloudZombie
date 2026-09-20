from app.detectors.base import Detector
from app.detectors.ebs_unattached import UnattachedEbsVolumeDetector

DETECTORS: list[Detector] = [UnattachedEbsVolumeDetector()]
