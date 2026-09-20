import re
from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.core.enums import ResourceType


class IdentifierKind(StrEnum):
    ACCOUNT_ID = "account_id"
    REGION = "region"
    VOLUME_ID = "volume_id"
    INSTANCE_ID = "instance_id"
    SNAPSHOT_ID = "snapshot_id"
    ALLOCATION_ID = "allocation_id"
    SCAN_ID = "scan_id"
    TAG_KEY = "tag_key"
    TAG_VALUE = "tag_value"


class InvalidIdentifierError(ValueError):
    def __init__(self, kind: IdentifierKind, value: object) -> None:
        self.kind = kind
        redacted = repr(str(value)[:20])
        super().__init__(f"invalid {kind.value}: {redacted}")


@dataclass(frozen=True)
class ValidatedIdentifier:
    kind: IdentifierKind
    value: str


_PATTERNS: dict[IdentifierKind, re.Pattern[str]] = {
    IdentifierKind.ACCOUNT_ID: re.compile(r"^\d{12}$"),
    IdentifierKind.REGION: re.compile(r"^[a-z]{2,4}(-[a-z]{2,12}){1,3}-\d$"),
    IdentifierKind.VOLUME_ID: re.compile(r"^vol-[0-9a-f]{8}(?:[0-9a-f]{9})?$"),
    IdentifierKind.INSTANCE_ID: re.compile(r"^i-[0-9a-f]{8}(?:[0-9a-f]{9})?$"),
    IdentifierKind.SNAPSHOT_ID: re.compile(r"^snap-[0-9a-f]{8}(?:[0-9a-f]{9})?$"),
    IdentifierKind.ALLOCATION_ID: re.compile(r"^eipalloc-[0-9a-f]{8}(?:[0-9a-f]{9})?$"),
    IdentifierKind.TAG_KEY: re.compile(r"^[A-Za-z0-9_.:/+@-]{1,128}$"),
    IdentifierKind.TAG_VALUE: re.compile(r"^[A-Za-z0-9_.:/+@-]{1,256}$"),
}


def _validate_pattern(kind: IdentifierKind, value: object) -> ValidatedIdentifier:
    if not isinstance(value, str) or any(character in value for character in ("\n", "\r", "\0")):
        raise InvalidIdentifierError(kind, value)
    if re.fullmatch(_PATTERNS[kind], value) is None:
        raise InvalidIdentifierError(kind, value)
    return ValidatedIdentifier(kind, value)


def validate_account_id(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.ACCOUNT_ID, value)


def validate_region(
    value: object, known_regions: Collection[str] | None = None
) -> ValidatedIdentifier:
    validated = _validate_pattern(IdentifierKind.REGION, value)
    if known_regions is not None and validated.value not in known_regions:
        raise InvalidIdentifierError(IdentifierKind.REGION, value)
    return validated


def validate_volume_id(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.VOLUME_ID, value)


def validate_instance_id(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.INSTANCE_ID, value)


def validate_snapshot_id(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.SNAPSHOT_ID, value)


def validate_allocation_id(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.ALLOCATION_ID, value)


def validate_scan_id(value: object) -> ValidatedIdentifier:
    kind = IdentifierKind.SCAN_ID
    if not isinstance(value, str) or any(character in value for character in ("\n", "\r", "\0")):
        raise InvalidIdentifierError(kind, value)
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvalidIdentifierError(kind, value) from exc
    if value.lower() != canonical:
        raise InvalidIdentifierError(kind, value)
    return ValidatedIdentifier(kind, canonical)


def validate_tag_key(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.TAG_KEY, value)


def validate_tag_value(value: object) -> ValidatedIdentifier:
    return _validate_pattern(IdentifierKind.TAG_VALUE, value)


_RESOURCE_VALIDATORS: dict[ResourceType, Callable[[object], ValidatedIdentifier]] = {
    ResourceType.EBS_VOLUME: validate_volume_id,
    ResourceType.ELASTIC_IP: validate_allocation_id,
    ResourceType.EC2_INSTANCE: validate_instance_id,
    ResourceType.EBS_SNAPSHOT: validate_snapshot_id,
}


def validate_resource_id(resource_type: ResourceType, value: object) -> ValidatedIdentifier:
    return _RESOURCE_VALIDATORS[resource_type](value)
