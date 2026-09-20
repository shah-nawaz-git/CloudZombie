import pytest

from app.core.enums import DetectorType, ScriptKind
from app.remediation.scripts.generator import ScriptTarget, generate_script
from tests.remediation.script_examples import (
    ACCOUNT,
    ADDRESS,
    EU,
    GENERATED_AT,
    IGNORE_KEY,
    IGNORE_VALUE,
    INSTANCE,
    SCAN_ID,
    VOLUME_ONE,
    generated_examples,
)


def test_all_script_shapes_are_ascii_and_have_expected_assignments() -> None:
    for script in generated_examples().values():
        assert script.content.startswith("#!/usr/bin/env bash\n")
        assert script.content.isascii()
        assert 'readonly EXPECTED_ACCOUNT_ID="123456789012"' in script.content
        assert script.filename.startswith("cloudzombie-")


def test_investigation_omits_guard_only_assignments() -> None:
    script = generated_examples()["ec2_investigation.sh"]
    assert "IGNORE_TAG_KEY" not in script.content
    assert "CLOUDFORMATION_TAG_KEY" not in script.content
    assert "read-only describe commands only" in script.checks


def test_snapshot_investigation_marks_delete_as_comment_only() -> None:
    script = generated_examples()["snapshot_investigation.sh"]
    assert "deletion command present only as a comment" in script.checks


def test_guarded_script_rejects_detector_without_destructive_body() -> None:
    with pytest.raises(ValueError):
        generate_script(
            kind=ScriptKind.GUARDED_REMEDIATION,
            detector_type=DetectorType.STOPPED_EC2_INSTANCE,
            account_id=ACCOUNT,
            target=ScriptTarget(EU, INSTANCE),
            scan_id=SCAN_ID,
            generated_at=GENERATED_AT,
            ignore_tag_key=IGNORE_KEY,
            ignore_tag_value=IGNORE_VALUE,
        )


def test_detector_and_resource_identifier_kind_must_match() -> None:
    with pytest.raises(ValueError):
        generate_script(
            kind=ScriptKind.GUARDED_REMEDIATION,
            detector_type=DetectorType.UNATTACHED_EBS_VOLUME,
            account_id=ACCOUNT,
            target=ScriptTarget(EU, ADDRESS),
            scan_id=SCAN_ID,
            generated_at=GENERATED_AT,
            ignore_tag_key=IGNORE_KEY,
            ignore_tag_value=IGNORE_VALUE,
        )


def test_guarded_ebs_checks_are_specific() -> None:
    script = generated_examples()["ebs_delete.sh"]
    assert f"exact confirmation phrase DELETE {VOLUME_ONE.value}" in script.checks
    assert any("snapshot" in warning.lower() for warning in script.warnings)
