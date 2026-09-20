from datetime import datetime
from typing import Any, Literal, Never, cast

from app.providers.base import (
    Address,
    Attachment,
    BlockDevice,
    Identity,
    Image,
    Instance,
    RegionInfo,
    Snapshot,
    SnapshotAttributes,
    SnapshotLock,
    StackResource,
    Volume,
)
from app.providers.errors import ProviderMalformedResponseError


def _malformed(message: str) -> Never:
    raise ProviderMalformedResponseError(message)


def _required(data: dict[str, Any], key: str) -> Any:
    if key not in data or data[key] is None:
        _malformed(f"missing required field {key}")
    return data[key]


def _datetime(data: dict[str, Any], key: str) -> datetime:
    value = _required(data, key)
    if not isinstance(value, datetime):
        _malformed(f"field {key} is not a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        _malformed(f"field {key} is not timezone-aware")
    return value


def map_tags(items: list[dict[str, Any]] | None) -> dict[str, str]:
    return {str(item["Key"]): str(item.get("Value", "")) for item in (items or []) if "Key" in item}


def map_volume(data: dict[str, Any]) -> Volume:
    return Volume(
        volume_id=str(_required(data, "VolumeId")),
        state=str(_required(data, "State")),
        volume_type=str(_required(data, "VolumeType")),
        size_gib=int(_required(data, "Size")),
        iops=int(data["Iops"]) if data.get("Iops") is not None else None,
        throughput_mibps=(int(data["Throughput"]) if data.get("Throughput") is not None else None),
        encrypted=bool(data.get("Encrypted", False)),
        created_at=_datetime(data, "CreateTime"),
        snapshot_id=str(data["SnapshotId"]) if data.get("SnapshotId") else None,
        attachments=tuple(
            Attachment(
                instance_id=str(_required(item, "InstanceId")),
                device=str(_required(item, "Device")),
                state=str(_required(item, "State")),
            )
            for item in data.get("Attachments", [])
        ),
        tags=map_tags(data.get("Tags")),
        availability_zone=str(_required(data, "AvailabilityZone")),
    )


def map_address(data: dict[str, Any]) -> Address:
    return Address(
        allocation_id=str(data["AllocationId"]) if data.get("AllocationId") else None,
        public_ip=str(_required(data, "PublicIp")),
        association_id=str(data["AssociationId"]) if data.get("AssociationId") else None,
        instance_id=str(data["InstanceId"]) if data.get("InstanceId") else None,
        network_interface_id=(
            str(data["NetworkInterfaceId"]) if data.get("NetworkInterfaceId") else None
        ),
        domain=str(data.get("Domain", "vpc")),
        tags=map_tags(data.get("Tags")),
    )


def map_instance(data: dict[str, Any]) -> Instance:
    return Instance(
        instance_id=str(_required(data, "InstanceId")),
        state=str(_required(data.get("State", {}), "Name")),
        instance_type=str(_required(data, "InstanceType")),
        launched_at=_datetime(data, "LaunchTime"),
        block_devices=tuple(
            BlockDevice(
                device_name=str(_required(item, "DeviceName")),
                volume_id=str(_required(item.get("Ebs", {}), "VolumeId")),
                status=str(item.get("Ebs", {}).get("Status", "attached")),
            )
            for item in data.get("BlockDeviceMappings", [])
            if item.get("Ebs")
        ),
        tags=map_tags(data.get("Tags")),
        platform=str(data["PlatformDetails"]) if data.get("PlatformDetails") else None,
    )


def map_snapshot(data: dict[str, Any]) -> Snapshot:
    return Snapshot(
        snapshot_id=str(_required(data, "SnapshotId")),
        volume_id=str(_required(data, "VolumeId")),
        owner_id=str(_required(data, "OwnerId")),
        state=str(_required(data, "State")),
        started_at=_datetime(data, "StartTime"),
        volume_size_gib=int(_required(data, "VolumeSize")),
        storage_tier=str(data.get("StorageTier", "standard")),
        encrypted=bool(data.get("Encrypted", False)),
        description=str(data.get("Description", "")),
        tags=map_tags(data.get("Tags")),
    )


def map_image(data: dict[str, Any]) -> Image:
    snapshot_ids = tuple(
        str(item["Ebs"]["SnapshotId"])
        for item in data.get("BlockDeviceMappings", [])
        if item.get("Ebs", {}).get("SnapshotId")
    )
    return Image(
        image_id=str(_required(data, "ImageId")),
        name=str(data.get("Name", "")),
        state=str(_required(data, "State")),
        snapshot_ids=snapshot_ids,
        tags=map_tags(data.get("Tags")),
    )


def map_region(data: dict[str, Any]) -> RegionInfo:
    opt_in_status = str(data.get("OptInStatus", "opt-in-not-required"))
    if opt_in_status not in {"opt-in-not-required", "opted-in", "not-opted-in"}:
        _malformed(f"invalid region opt-in status {opt_in_status}")
    valid_status = cast(Literal["opt-in-not-required", "opted-in", "not-opted-in"], opt_in_status)
    return RegionInfo(
        name=str(_required(data, "RegionName")),
        opt_in_status=valid_status,
    )


def map_identity(data: dict[str, Any]) -> Identity:
    arn = str(_required(data, "Arn"))
    identity_type: Literal["role", "user", "assumed-role", "root", "unknown"]
    if ":assumed-role/" in arn:
        identity_type = "assumed-role"
    elif ":role/" in arn:
        identity_type = "role"
    elif ":user/" in arn:
        identity_type = "user"
    elif arn.endswith(":root"):
        identity_type = "root"
    else:
        identity_type = "unknown"
    return Identity(
        account_id=str(_required(data, "Account")),
        principal_arn=arn,
        identity_type=identity_type,
        user_id=str(_required(data, "UserId")),
    )


def map_snapshot_attributes(data: dict[str, Any]) -> SnapshotAttributes:
    permissions = data.get("CreateVolumePermissions", [])
    return SnapshotAttributes(
        snapshot_id=str(_required(data, "SnapshotId")),
        shared_user_ids=tuple(str(item["UserId"]) for item in permissions if item.get("UserId")),
        shared_groups=tuple(str(item["Group"]) for item in permissions if item.get("Group")),
    )


def map_snapshot_lock(data: dict[str, Any]) -> SnapshotLock:
    raw_lock_state = data.get("LockState")
    if raw_lock_state not in {None, "compliance", "governance", "compliance-cooloff", "expired"}:
        _malformed(f"invalid snapshot lock state {raw_lock_state}")
    lock_state: Literal["compliance", "governance", "compliance-cooloff", "expired"] | None = (
        raw_lock_state
    )
    return SnapshotLock(
        snapshot_id=str(_required(data, "SnapshotId")),
        lock_state=lock_state,
    )


def map_stack_resource(region: str, stack: dict[str, Any], data: dict[str, Any]) -> StackResource:
    return StackResource(
        region=region,
        stack_name=str(_required(stack, "StackName")),
        stack_id=str(_required(stack, "StackId")),
        logical_id=str(_required(data, "LogicalResourceId")),
        physical_id=str(data["PhysicalResourceId"]) if data.get("PhysicalResourceId") else None,
        resource_type=str(_required(data, "ResourceType")),
        resource_status=str(_required(data, "ResourceStatus")),
    )
