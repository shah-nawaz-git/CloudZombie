import re
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.clock import FixedClock
from app.core.enums import (
    DetectorType,
    PersistenceState,
    RemediationRisk,
    ResourceType,
)
from app.models import AppSettings
from app.remediation.validators import InvalidIdentifierError
from app.services.script_service import ScriptService
from tests.remediation.finding_factory import NOW, make_finding

HOSTILE = [
    "$(rm -rf /)",
    '"; echo hacked',
    "`id`",
    "value\nwith\nnewlines",
    "'; drop table findings; --",
    "${HOME}",
    "‚ÄùÔøΩ",
]
_READONLY = re.compile(r'^readonly ([A-Z_]+)="([^"]*)"$')


def hostile_finding(**changes):
    payload = {value: value for value in HOSTILE}
    values = {
        "title": HOSTILE[0],
        "summary": HOSTILE[1],
        "evidence": {"payload": payload},
        "ignore_reason": HOSTILE[2],
        "ownership": {"status": "UNKNOWN", "notes": HOSTILE},
    }
    values.update(changes)
    return make_finding(**values)


def all_script_findings():
    return [
        hostile_finding(),
        hostile_finding(
            id=UUID("22222222-2222-4222-8222-222222222223"),
            resource_type=ResourceType.ELASTIC_IP.value,
            resource_id="eipalloc-0a1b2c3d4e5f60001",
            detector_type=DetectorType.UNASSOCIATED_ELASTIC_IP.value,
        ),
        hostile_finding(
            id=UUID("22222222-2222-4222-8222-222222222224"),
            persistence_state=PersistenceState.NEWLY_OBSERVED.value,
            remediation_risk=RemediationRisk.REVIEW.value,
        ),
        hostile_finding(
            id=UUID("22222222-2222-4222-8222-222222222225"),
            resource_type=ResourceType.ELASTIC_IP.value,
            resource_id="eipalloc-0a1b2c3d4e5f60002",
            detector_type=DetectorType.UNASSOCIATED_ELASTIC_IP.value,
            remediation_risk=RemediationRisk.HIGH.value,
        ),
        hostile_finding(
            id=UUID("22222222-2222-4222-8222-222222222226"),
            resource_type=ResourceType.EC2_INSTANCE.value,
            resource_id="i-0a1b2c3d4e5f60001",
            detector_type=DetectorType.STOPPED_EC2_INSTANCE.value,
            remediation_risk=RemediationRisk.REVIEW.value,
        ),
        hostile_finding(
            id=UUID("22222222-2222-4222-8222-222222222227"),
            resource_type=ResourceType.EBS_SNAPSHOT.value,
            resource_id="snap-0a1b2c3d4e5f60001",
            detector_type=DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME.value,
            remediation_risk=RemediationRisk.HIGH.value,
        ),
    ]


def test_untrusted_finding_metadata_never_reaches_scripts() -> None:
    service = ScriptService(AppSettings(), FixedClock(NOW))
    allowed_values = {
        "123456789012",
        "eu-central-1",
        "vol-0a1b2c3d4e5f60001",
        "eipalloc-0a1b2c3d4e5f60001",
        "eipalloc-0a1b2c3d4e5f60002",
        "i-0a1b2c3d4e5f60001",
        "snap-0a1b2c3d4e5f60001",
        "cloudzombie:ignore",
        "true",
        "aws:cloudformation:stack-name",
    }
    for finding in all_script_findings():
        content = service.for_finding(finding).content
        assert content.isascii()
        assert not any(value in content for value in HOSTILE)
        for line in content.splitlines():
            match = _READONLY.fullmatch(line)
            if match:
                assert match.group(2) in allowed_values


@pytest.mark.parametrize(
    "changes",
    [
        {"resource_id": "vol-0a1b; rm -rf /"},
        {"region": "eu-central-1; echo"},
        {"account_id": "12345678901"},
    ],
)
def test_malformed_stored_identifier_fails_before_content(changes) -> None:
    service = ScriptService(AppSettings(), FixedClock(NOW))
    with pytest.raises(InvalidIdentifierError):
        service.for_finding(make_finding(**changes))


def test_unsafe_ignore_setting_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(ignore_tag_key="cloud zombie")
