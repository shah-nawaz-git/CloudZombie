from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.enums import Mode


@dataclass(frozen=True)
class Identity:
    account_id: str
    principal_arn: str
    identity_type: Literal["role", "user", "assumed-role", "root", "unknown"]
    user_id: str


@dataclass(frozen=True)
class RegionInfo:
    name: str
    opt_in_status: Literal["opt-in-not-required", "opted-in", "not-opted-in"]


@dataclass(frozen=True)
class Attachment:
    instance_id: str
    device: str
    state: str


@dataclass(frozen=True)
class Volume:
    volume_id: str
    state: str
    volume_type: str
    size_gib: int
    iops: int | None
    throughput_mibps: int | None
    encrypted: bool
    created_at: datetime
    snapshot_id: str | None
    attachments: tuple[Attachment, ...]
    tags: Mapping[str, str]
    availability_zone: str


@dataclass(frozen=True)
class Address:
    allocation_id: str | None
    public_ip: str
    association_id: str | None
    instance_id: str | None
    network_interface_id: str | None
    domain: str
    tags: Mapping[str, str]


@dataclass(frozen=True)
class BlockDevice:
    device_name: str
    volume_id: str
    status: str


@dataclass(frozen=True)
class Instance:
    instance_id: str
    state: str
    instance_type: str
    launched_at: datetime
    block_devices: tuple[BlockDevice, ...]
    tags: Mapping[str, str]
    platform: str | None


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    volume_id: str
    owner_id: str
    state: str
    started_at: datetime
    volume_size_gib: int
    storage_tier: str
    encrypted: bool
    description: str
    tags: Mapping[str, str]


@dataclass(frozen=True)
class Image:
    image_id: str
    name: str
    state: str
    snapshot_ids: tuple[str, ...]
    tags: Mapping[str, str]


@dataclass(frozen=True)
class SnapshotAttributes:
    snapshot_id: str
    shared_user_ids: tuple[str, ...]
    shared_groups: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotLock:
    snapshot_id: str
    lock_state: Literal["compliance", "governance", "compliance-cooloff", "expired"] | None


@dataclass(frozen=True)
class StackResource:
    region: str
    stack_name: str
    stack_id: str
    logical_id: str
    physical_id: str | None
    resource_type: str
    resource_status: str


class CloudProvider(ABC):
    mode: Mode

    @abstractmethod
    def get_identity(self) -> Identity: ...

    @abstractmethod
    def list_regions(self) -> list[RegionInfo]: ...

    @abstractmethod
    def list_volumes(self, region: str) -> list[Volume]: ...

    @abstractmethod
    def list_addresses(self, region: str) -> list[Address]: ...

    @abstractmethod
    def list_instances(self, region: str) -> list[Instance]: ...

    @abstractmethod
    def list_snapshots(self, region: str) -> list[Snapshot]: ...

    @abstractmethod
    def list_images(self, region: str) -> list[Image]: ...

    @abstractmethod
    def get_snapshot_attributes(self, region: str, snapshot_id: str) -> SnapshotAttributes: ...

    @abstractmethod
    def get_snapshot_locks(
        self, region: str, snapshot_ids: Sequence[str]
    ) -> list[SnapshotLock]: ...

    @abstractmethod
    def list_stack_resources(self, region: str) -> list[StackResource]: ...

    @abstractmethod
    def get_prices(self, service_code: str, filters: Sequence[tuple[str, str]]) -> list[dict]: ...
