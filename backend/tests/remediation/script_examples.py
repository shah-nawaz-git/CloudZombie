from datetime import UTC, datetime

from app.core.enums import DetectorType, ScriptKind
from app.remediation.scripts.generator import (
    GeneratedScript,
    ScriptTarget,
    generate_bulk_script,
    generate_script,
)
from app.remediation.validators import (
    validate_account_id,
    validate_allocation_id,
    validate_instance_id,
    validate_region,
    validate_scan_id,
    validate_snapshot_id,
    validate_tag_key,
    validate_tag_value,
    validate_volume_id,
)

GENERATED_AT = datetime(2026, 9, 20, 10, tzinfo=UTC)
ACCOUNT = validate_account_id("123456789012")
SCAN_ID = validate_scan_id("11111111-1111-4111-8111-111111111111")
IGNORE_KEY = validate_tag_key("cloudzombie:ignore")
IGNORE_VALUE = validate_tag_value("true")
EU = validate_region("eu-central-1")
US = validate_region("us-east-1")
VOLUME_ONE = validate_volume_id("vol-0a1b2c3d4e5f60001")
VOLUME_TWO = validate_volume_id("vol-0a1b2c3d4e5f60002")
ADDRESS = validate_allocation_id("eipalloc-0a1b2c3d4e5f60001")
INSTANCE = validate_instance_id("i-0a1b2c3d4e5f60001")
SNAPSHOT = validate_snapshot_id("snap-0a1b2c3d4e5f60001")


def single(kind: ScriptKind, detector: DetectorType, target: ScriptTarget) -> GeneratedScript:
    return generate_script(
        kind=kind,
        detector_type=detector,
        account_id=ACCOUNT,
        target=target,
        scan_id=SCAN_ID,
        generated_at=GENERATED_AT,
        ignore_tag_key=IGNORE_KEY,
        ignore_tag_value=IGNORE_VALUE,
    )


def generated_examples() -> dict[str, GeneratedScript]:
    return {
        "ebs_delete.sh": single(
            ScriptKind.GUARDED_REMEDIATION,
            DetectorType.UNATTACHED_EBS_VOLUME,
            ScriptTarget(EU, VOLUME_ONE),
        ),
        "eip_release.sh": single(
            ScriptKind.GUARDED_REMEDIATION,
            DetectorType.UNASSOCIATED_ELASTIC_IP,
            ScriptTarget(US, ADDRESS),
        ),
        "ebs_investigation.sh": single(
            ScriptKind.INVESTIGATION,
            DetectorType.UNATTACHED_EBS_VOLUME,
            ScriptTarget(EU, VOLUME_ONE),
        ),
        "eip_investigation.sh": single(
            ScriptKind.INVESTIGATION,
            DetectorType.UNASSOCIATED_ELASTIC_IP,
            ScriptTarget(US, ADDRESS),
        ),
        "ec2_investigation.sh": single(
            ScriptKind.INVESTIGATION,
            DetectorType.STOPPED_EC2_INSTANCE,
            ScriptTarget(US, INSTANCE),
        ),
        "snapshot_investigation.sh": single(
            ScriptKind.INVESTIGATION,
            DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME,
            ScriptTarget(EU, SNAPSHOT),
        ),
        "bulk.sh": generate_bulk_script(
            account_id=ACCOUNT,
            targets=[
                (
                    DetectorType.UNATTACHED_EBS_VOLUME,
                    ScriptTarget(EU, VOLUME_ONE),
                ),
                (
                    DetectorType.UNATTACHED_EBS_VOLUME,
                    ScriptTarget(US, VOLUME_TWO),
                ),
                (
                    DetectorType.UNASSOCIATED_ELASTIC_IP,
                    ScriptTarget(US, ADDRESS),
                ),
            ],
            scan_id=SCAN_ID,
            generated_at=GENERATED_AT,
            ignore_tag_key=IGNORE_KEY,
            ignore_tag_value=IGNORE_VALUE,
        ),
    }
