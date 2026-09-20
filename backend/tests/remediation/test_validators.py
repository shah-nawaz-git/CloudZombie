import pytest

from app.core.enums import ResourceType
from app.remediation.validators import (
    IdentifierKind,
    InvalidIdentifierError,
    validate_account_id,
    validate_allocation_id,
    validate_instance_id,
    validate_region,
    validate_resource_id,
    validate_scan_id,
    validate_snapshot_id,
    validate_tag_key,
    validate_tag_value,
    validate_volume_id,
)


@pytest.mark.parametrize(
    ("validator", "legacy", "modern"),
    [
        (validate_volume_id, "vol-0a1b2c3d", "vol-0a1b2c3d4e5f60001"),
        (validate_instance_id, "i-0a1b2c3d", "i-0a1b2c3d4e5f60001"),
        (validate_snapshot_id, "snap-0a1b2c3d", "snap-0a1b2c3d4e5f60001"),
        (
            validate_allocation_id,
            "eipalloc-0a1b2c3d",
            "eipalloc-0a1b2c3d4e5f60001",
        ),
    ],
)
def test_resource_validators_accept_legacy_and_modern_ids(validator, legacy, modern) -> None:
    assert validator(legacy).value == legacy
    assert validator(modern).value == modern


@pytest.mark.parametrize(
    "value",
    [
        "vol-0a1b2c3d4e5f6001",
        "vol-0A1B2C3D4E5F60001",
        "snap-0a1b2c3d4e5f60001",
        "vol-0a1b2c3d4e5f60001; rm -rf /",
        "vol-0a1b2c3d4e5f60001\n",
        "$(id)",
        "",
        None,
        123,
    ],
)
def test_volume_validator_rejects_malformed_and_hostile_values(value) -> None:
    with pytest.raises(InvalidIdentifierError) as caught:
        validate_volume_id(value)
    assert caught.value.kind == IdentifierKind.VOLUME_ID
    assert len(str(caught.value)) < 60


@pytest.mark.parametrize("value", ["12345678901", "1234567890123", "123456789012 "])
def test_account_rejections(value) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_account_id(value)


@pytest.mark.parametrize(
    "value",
    ["us-east-1", "eu-central-1", "ap-southeast-3", "us-gov-west-1", "eusc-de-east-1"],
)
def test_regions_accepted(value) -> None:
    assert validate_region(value).value == value


@pytest.mark.parametrize("value", ["us-east-1; echo", "US-EAST-1", "useast1"])
def test_regions_rejected(value) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_region(value)


def test_known_region_membership() -> None:
    assert validate_region("us-east-1", {"us-east-1"}).value == "us-east-1"
    with pytest.raises(InvalidIdentifierError):
        validate_region("eu-central-1", {"us-east-1"})


def test_scan_id_uppercase_is_normalized() -> None:
    value = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    assert validate_scan_id(value).value == value.lower()


@pytest.mark.parametrize("value", ["cloud zombie", 'cloudzombie:"x"', "cloud$zombie", "`id`"])
def test_tag_key_rejects_shell_metacharacters(value) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_tag_key(value)


@pytest.mark.parametrize("value", ["has space", 'say"hello', "$HOME", "`id`"])
def test_tag_value_rejects_shell_metacharacters(value) -> None:
    with pytest.raises(InvalidIdentifierError):
        validate_tag_value(value)


def test_resource_dispatch() -> None:
    assert (
        validate_resource_id(ResourceType.EBS_VOLUME, "vol-0a1b2c3d4e5f60001").kind
        == IdentifierKind.VOLUME_ID
    )
