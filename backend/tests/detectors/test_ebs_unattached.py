from app.core.enums import DetectionConfidence
from app.detectors.base import ScanContext
from app.detectors.ebs_unattached import UnattachedEbsVolumeDetector
from app.models import AppSettings, EbsVolumePricingRequest
from tests.conftest import make_volume


class Provider:
    def __init__(self, volumes):
        self.volumes = volumes

    def list_volumes(self, region):
        return self.volumes


def scan(volume, fixed_clock):
    context = ScanContext("123456789012", "us-east-1", fixed_clock.now(), AppSettings())
    return UnattachedEbsVolumeDetector().scan(Provider([volume]), "us-east-1", context)


def test_available_without_attachments_emits_high_confidence(fixed_clock) -> None:
    candidates = scan(make_volume(), fixed_clock)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.detection_confidence == DetectionConfidence.HIGH
    assert isinstance(candidate.pricing_request, EbsVolumePricingRequest)
    assert candidate.pricing_request.size_gib == 100
    assert not hasattr(candidate, "estimated_monthly_cost")
    assert set(candidate.evidence) == {
        "volume_id",
        "availability_zone",
        "state",
        "volume_type",
        "size_gib",
        "iops",
        "throughput_mibps",
        "encrypted",
        "created_at",
        "origin_snapshot_id",
        "attachment_count",
        "tags",
        "name_tag",
    }


def test_non_available_states_do_not_emit(fixed_clock) -> None:
    for state in ("in-use", "creating", "deleting"):
        assert scan(make_volume(state=state), fixed_clock) == []


def test_ignore_tag_emits_ignored_candidate(fixed_clock) -> None:
    candidate = scan(
        make_volume(tags={"cloudzombie:ignore": "TRUE", "cloudzombie:reason": "DR"}),
        fixed_clock,
    )[0]
    assert candidate.ignored is True
    assert candidate.ignore_reason == "DR"
