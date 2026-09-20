import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.enums import DetectorType
from app.remediation.scripts.generator import ScriptTarget, generate_bulk_script
from tests.remediation.script_examples import (
    ACCOUNT,
    EU,
    GENERATED_AT,
    IGNORE_KEY,
    IGNORE_VALUE,
    SCAN_ID,
    US,
    VOLUME_ONE,
    VOLUME_TWO,
    generated_examples,
)

FAKE_AWS = Path(__file__).with_name("fake_aws") / "aws"


def run_script(tmp_path, content, stdin="", **fake_env):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")
    FAKE_AWS.chmod(0o755)
    script = tmp_path / "script.sh"
    script.write_text(content, encoding="ascii", newline="\n")
    log = tmp_path / "aws.log"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": str(FAKE_AWS.parent) + os.pathsep + environment.get("PATH", ""),
            "FAKE_LOG": str(log),
            **fake_env,
        }
    )
    result = subprocess.run(
        [bash, str(script)],
        input=stdin.encode("utf-8"),
        capture_output=True,
        env=environment,
        check=False,
    )
    result.stdout = result.stdout.decode("utf-8")
    result.stderr = result.stderr.decode("utf-8")
    invocations = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    for invocation in invocations:
        if invocation.startswith("ec2 "):
            assert "--region " in invocation
    return result, invocations


def mutation_count(invocations, operation):
    return sum(f"ec2 {operation} " in invocation for invocation in invocations)


def test_ebs_happy_path(tmp_path) -> None:
    script = generated_examples()["ebs_delete.sh"]
    result, log = run_script(tmp_path, script.content, f"n\nDELETE {VOLUME_ONE.value}\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Account verified" in result.stdout
    assert mutation_count(log, "delete-volume") == 1


def test_account_mismatch_aborts(tmp_path) -> None:
    result, log = run_script(
        tmp_path,
        generated_examples()["ebs_delete.sh"].content,
        FAKE_ACCOUNT="999999999999",
    )
    assert result.returncode == 1
    assert "ABORTED" in result.stdout
    assert "Expected account: 123456789012" in result.stdout
    assert "Current account:  999999999999" in result.stdout
    assert "No action performed." in result.stdout
    assert mutation_count(log, "delete-volume") == 0


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"FAKE_VOLUME_STATE": "in-use"}, "Resource state changed since CloudZombie analysis"),
        ({"FAKE_ATTACHMENTS": "1"}, "Resource state changed since CloudZombie analysis"),
        ({"FAKE_VOLUME_MISSING": "1"}, "not found"),
        ({"FAKE_IGNORE_VALUE": "true"}, "marked to be ignored"),
        ({"FAKE_IGNORE_VALUE": "TRUE"}, "marked to be ignored"),
        ({"FAKE_STACK_NAME": "customer-api-prod"}, "CloudFormation"),
    ],
)
def test_ebs_safety_abort_conditions(tmp_path, environment, message) -> None:
    result, log = run_script(tmp_path, generated_examples()["ebs_delete.sh"].content, **environment)
    assert result.returncode == 1
    assert "ABORTED" in result.stdout
    assert message in result.stdout
    assert mutation_count(log, "delete-volume") == 0


def test_wrong_confirmation_aborts(tmp_path) -> None:
    result, log = run_script(
        tmp_path, generated_examples()["ebs_delete.sh"].content, "n\nDELETE vol-other\n"
    )
    assert result.returncode == 1
    assert "Confirmation did not match" in result.stdout
    assert mutation_count(log, "delete-volume") == 0


def test_eip_happy_path(tmp_path) -> None:
    script = generated_examples()["eip_release.sh"]
    allocation = "eipalloc-0a1b2c3d4e5f60001"
    result, log = run_script(tmp_path, script.content, f"RELEASE {allocation}\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert mutation_count(log, "release-address") == 1


@pytest.mark.parametrize(
    "environment",
    [
        {"FAKE_ASSOCIATION_ID": "eipassoc-1"},
        {"FAKE_INSTANCE_ID": "i-1"},
        {"FAKE_ENI_ID": "eni-1"},
        {"FAKE_ADDRESS_MISSING": "1"},
    ],
)
def test_eip_associated_or_missing_aborts(tmp_path, environment) -> None:
    result, log = run_script(
        tmp_path, generated_examples()["eip_release.sh"].content, **environment
    )
    assert result.returncode == 1
    assert "ABORTED" in result.stdout
    assert mutation_count(log, "release-address") == 0


def test_bulk_skips_changed_first_volume_and_deletes_second(tmp_path) -> None:
    script = generate_bulk_script(
        account_id=ACCOUNT,
        targets=[
            (DetectorType.UNATTACHED_EBS_VOLUME, ScriptTarget(EU, VOLUME_ONE)),
            (DetectorType.UNATTACHED_EBS_VOLUME, ScriptTarget(US, VOLUME_TWO)),
        ],
        scan_id=SCAN_ID,
        generated_at=GENERATED_AT,
        ignore_tag_key=IGNORE_KEY,
        ignore_tag_value=IGNORE_VALUE,
    )
    result, log = run_script(
        tmp_path,
        script.content,
        f"DELETE {VOLUME_TWO.value}\n",
        FAKE_CHANGED_VOLUME_ID=VOLUME_ONE.value,
        FAKE_VOLUME_STATE="in-use",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIPPED" in result.stdout
    assert "Completed: 1   Skipped: 1" in result.stdout
    assert mutation_count(log, "delete-volume") == 1


def test_investigation_scripts_complete_without_mutations(tmp_path) -> None:
    for filename in (
        "ebs_investigation.sh",
        "eip_investigation.sh",
        "ec2_investigation.sh",
        "snapshot_investigation.sh",
    ):
        case_dir = tmp_path / filename
        case_dir.mkdir()
        result, log = run_script(case_dir, generated_examples()[filename].content)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not any(
            operation in invocation
            for invocation in log
            for operation in ("delete-", "release-", "terminate-")
        )
