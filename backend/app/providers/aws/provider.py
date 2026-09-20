import time
from collections.abc import Callable, Sequence
from threading import Lock
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    NoCredentialsError,
    NoRegionError,
    PartialCredentialsError,
    ProfileNotFound,
)

from app.core.enums import Mode
from app.providers.aws.errors import translate_client_error
from app.providers.aws.guard import guarded_client, install_operation_guard
from app.providers.aws.mapping import (
    map_address,
    map_identity,
    map_image,
    map_instance,
    map_region,
    map_snapshot,
    map_snapshot_attributes,
    map_snapshot_lock,
    map_stack_resource,
    map_volume,
    parse_price_list,
)
from app.providers.aws.readonly import (
    ReadOnlyCloudFormation,
    ReadOnlyEc2,
    ReadOnlyPricing,
    ReadOnlySts,
)
from app.providers.base import (
    Address,
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


class AwsProvider(CloudProvider):
    mode = Mode.LIVE

    def __init__(
        self,
        profile_name: str | None = None,
        default_region: str | None = None,
        session: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        try:
            self.__session = session or boto3.Session(
                profile_name=profile_name, region_name=default_region
            )
            install_operation_guard(self.__session)
            self.__config = Config(
                retries={"mode": "standard", "max_attempts": 6},
                connect_timeout=10,
                read_timeout=60,
                user_agent_extra="CloudZombie/0.1 (read-only)",
            )
            home_region = self.__session.region_name or "us-east-1"
            self.__sts = ReadOnlySts(
                guarded_client(self.__session, "sts", home_region, config=self.__config),
                sleep=sleep,
            )
            self.__regions = ReadOnlyEc2(
                guarded_client(self.__session, "ec2", home_region, config=self.__config),
                sleep=sleep,
            )
            self.__pricing = ReadOnlyPricing(
                guarded_client(self.__session, "pricing", "us-east-1", config=self.__config),
                sleep=sleep,
            )
        except (
            NoCredentialsError,
            NoRegionError,
            PartialCredentialsError,
            ProfileNotFound,
        ) as exc:
            translate_client_error(exc, "aws:CreateSession", default_region)
        self.__sleep = sleep
        self.__ec2_by_region: dict[str, ReadOnlyEc2] = {}
        self.__cloudformation_by_region: dict[str, ReadOnlyCloudFormation] = {}
        self.__wrapper_lock = Lock()

    def __ec2(self, region: str) -> ReadOnlyEc2:
        with self.__wrapper_lock:
            wrapper = self.__ec2_by_region.get(region)
            if wrapper is None:
                wrapper = ReadOnlyEc2(
                    guarded_client(self.__session, "ec2", region, config=self.__config),
                    sleep=self.__sleep,
                )
                self.__ec2_by_region[region] = wrapper
            return wrapper

    def __cloudformation(self, region: str) -> ReadOnlyCloudFormation:
        with self.__wrapper_lock:
            wrapper = self.__cloudformation_by_region.get(region)
            if wrapper is None:
                wrapper = ReadOnlyCloudFormation(
                    guarded_client(
                        self.__session,
                        "cloudformation",
                        region,
                        config=self.__config,
                    ),
                    sleep=self.__sleep,
                )
                self.__cloudformation_by_region[region] = wrapper
            return wrapper

    def get_identity(self) -> Identity:
        return map_identity(self.__sts.get_caller_identity())

    def list_regions(self) -> list[RegionInfo]:
        response = self.__regions.describe_regions()
        return [map_region(item) for item in response.get("Regions", [])]

    def list_volumes(self, region: str) -> list[Volume]:
        response = self.__ec2(region).describe_volumes()
        return [map_volume(item) for item in response.get("Volumes", [])]

    def list_addresses(self, region: str) -> list[Address]:
        response = self.__ec2(region).describe_addresses()
        return [map_address(item) for item in response.get("Addresses", [])]

    def list_instances(self, region: str) -> list[Instance]:
        response = self.__ec2(region).describe_instances()
        return [
            map_instance(instance)
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

    def list_snapshots(self, region: str) -> list[Snapshot]:
        response = self.__ec2(region).describe_snapshots()
        return [map_snapshot(item) for item in response.get("Snapshots", [])]

    def list_images(self, region: str) -> list[Image]:
        response = self.__ec2(region).describe_images()
        return [map_image(item) for item in response.get("Images", [])]

    def get_snapshot_attributes(self, region: str, snapshot_id: str) -> SnapshotAttributes:
        response = self.__ec2(region).describe_snapshot_attribute(snapshot_id)
        return map_snapshot_attributes(response)

    def get_snapshot_locks(self, region: str, snapshot_ids: Sequence[str]) -> list[SnapshotLock]:
        if not snapshot_ids:
            return []
        response = self.__ec2(region).describe_locked_snapshots(list(snapshot_ids))
        return [map_snapshot_lock(item) for item in response.get("Snapshots", [])]

    def list_stack_resources(self, region: str) -> list[StackResource]:
        wrapper = self.__cloudformation(region)
        stack_response = wrapper.list_stacks()
        resources: list[StackResource] = []
        for stack in stack_response.get("StackSummaries", []):
            if stack.get("StackStatus") == "DELETE_COMPLETE":
                continue
            resource_response = wrapper.list_stack_resources(str(stack["StackName"]))
            resources.extend(
                map_stack_resource(region, stack, item)
                for item in resource_response.get("StackResourceSummaries", [])
            )
        return resources

    def get_prices(self, service_code: str, filters: Sequence[tuple[str, str]]) -> list[dict]:
        request_filters = [
            {"Type": "TERM_MATCH", "Field": field, "Value": value} for field, value in filters
        ]
        response = self.__pricing.get_products(service_code, request_filters)
        return parse_price_list(response.get("PriceList", []))
