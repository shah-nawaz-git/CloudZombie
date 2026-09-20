import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.enums import Mode
from app.providers.base import (
    Address,
    Attachment,
    BlockDevice,
    CloudProvider,
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
from app.providers.errors import ProviderPermissionError, ProviderTransientError


@dataclass(frozen=True)
class DemoDataset:
    data: dict[str, Any]


def load_demo_dataset(path: str | Path | None = None) -> DemoDataset:
    if path is None:
        path = Path(__file__).resolve().parents[3] / "fixtures" / "demo" / "dataset.json"
    with Path(path).open(encoding="utf-8") as handle:
        return DemoDataset(json.load(handle))


class DemoProvider(CloudProvider):
    mode = Mode.DEMO

    def __init__(self, dataset: DemoDataset, step: int, anchor: datetime) -> None:
        if anchor.tzinfo is None or anchor.utcoffset() is None:
            raise ValueError("demo anchor must be timezone-aware")
        self._data = dataset.data
        self._step = step
        self._anchor = anchor.astimezone(UTC)

    def _items(self, key: str, region: str | None = None) -> list[dict[str, Any]]:
        return [
            item
            for item in self._data.get(key, [])
            if self._step in item.get("steps", [])
            and (region is None or item.get("region") == region)
        ]

    def _created_at(self, item: dict[str, Any]) -> datetime:
        return self._anchor - timedelta(days=int(item["created_days_ago"]))

    def _fault(self, method: str, region: str) -> None:
        for fault in self._data.get("faults", []):
            if (
                fault["method"] == method
                and fault["region"] == region
                and fault["kind"] == "access_denied"
            ):
                operations = {
                    "list_snapshots": "ec2:DescribeSnapshots",
                    "list_volumes": "ec2:DescribeVolumes",
                }
                raise ProviderPermissionError(operations.get(method, method), region)

    def get_identity(self) -> Identity:
        return Identity(
            account_id=self._data["account_id"],
            principal_arn=self._data["principal_arn"],
            identity_type="assumed-role",
            user_id=self._data["user_id"],
        )

    def list_regions(self) -> list[RegionInfo]:
        return [RegionInfo(**item) for item in self._data["regions"]]

    def list_volumes(self, region: str) -> list[Volume]:
        self._fault("list_volumes", region)
        return [
            Volume(
                volume_id=item["volume_id"],
                state=item["state"],
                volume_type=item["volume_type"],
                size_gib=item["size_gib"],
                iops=item.get("iops"),
                throughput_mibps=item.get("throughput_mibps"),
                encrypted=item["encrypted"],
                created_at=self._created_at(item),
                snapshot_id=item.get("snapshot_id"),
                attachments=tuple(Attachment(**attachment) for attachment in item["attachments"]),
                tags=item["tags"],
                availability_zone=item["availability_zone"],
            )
            for item in self._items("volumes", region)
        ]

    def list_addresses(self, region: str) -> list[Address]:
        self._fault("list_addresses", region)
        return [
            Address(**{key: value for key, value in item.items() if key not in {"region", "steps"}})
            for item in self._items("addresses", region)
        ]

    def list_instances(self, region: str) -> list[Instance]:
        self._fault("list_instances", region)
        return [
            Instance(
                instance_id=item["instance_id"],
                state=item["state"],
                instance_type=item["instance_type"],
                launched_at=self._created_at(item),
                block_devices=tuple(BlockDevice(**device) for device in item["block_devices"]),
                tags=item["tags"],
                platform=item.get("platform"),
            )
            for item in self._items("instances", region)
        ]

    def list_snapshots(self, region: str) -> list[Snapshot]:
        self._fault("list_snapshots", region)
        return [
            Snapshot(
                snapshot_id=item["snapshot_id"],
                volume_id=item["volume_id"],
                owner_id=item["owner_id"],
                state=item["state"],
                started_at=self._created_at(item),
                volume_size_gib=item["volume_size_gib"],
                storage_tier=item["storage_tier"],
                encrypted=item["encrypted"],
                description=item["description"],
                tags=item["tags"],
            )
            for item in self._items("snapshots", region)
        ]

    def list_images(self, region: str) -> list[Image]:
        self._fault("list_images", region)
        return [
            Image(
                image_id=item["image_id"],
                name=item["name"],
                state=item["state"],
                snapshot_ids=tuple(item["snapshot_ids"]),
                tags=item["tags"],
            )
            for item in self._items("images", region)
        ]

    def get_snapshot_attributes(self, region: str, snapshot_id: str) -> SnapshotAttributes:
        self._fault("get_snapshot_attributes", region)
        attributes = self._data.get("snapshot_attributes", {}).get(snapshot_id, {})
        return SnapshotAttributes(
            snapshot_id=snapshot_id,
            shared_user_ids=tuple(attributes.get("shared_user_ids", [])),
            shared_groups=tuple(attributes.get("shared_groups", [])),
        )

    def get_snapshot_locks(self, region: str, snapshot_ids: Sequence[str]) -> list[SnapshotLock]:
        self._fault("get_snapshot_locks", region)
        requested = set(snapshot_ids)
        return [
            SnapshotLock(snapshot_id=item["snapshot_id"], lock_state=item.get("lock_state"))
            for item in self._data.get("snapshot_locks", [])
            if item["snapshot_id"] in requested
        ]

    def list_stack_resources(self, region: str) -> list[StackResource]:
        self._fault("list_stack_resources", region)
        return [
            StackResource(
                region=item["region"],
                stack_name=item["stack_name"],
                stack_id=item["stack_id"],
                logical_id=item["logical_id"],
                physical_id=item.get("physical_id"),
                resource_type=item["resource_type"],
                resource_status=item["resource_status"],
            )
            for item in self._items("stack_resources", region)
        ]

    def get_prices(self, service_code: str, filters: Sequence[tuple[str, str]]) -> list[dict]:
        raise ProviderTransientError("pricing API not available in demo mode")
