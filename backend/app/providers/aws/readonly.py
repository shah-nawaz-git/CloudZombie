import time
from collections.abc import Callable
from typing import Any

from app.providers.aws.errors import THROTTLING_CODES, client_error_code, translate_client_error

Sleep = Callable[[float], None]


def _invoke(
    client: Any,
    method_name: str,
    operation: str,
    region: str | None,
    sleep: Sleep,
    **kwargs: Any,
) -> dict[str, Any]:
    for attempt in range(4):
        try:
            method = getattr(client, method_name)
            return dict(method(**kwargs))
        except Exception as exc:
            code, _ = client_error_code(exc)
            if code in THROTTLING_CODES and attempt < 3:
                sleep(min(0.5 * (2**attempt), 8.0))
                continue
            translate_client_error(exc, operation, region)
    raise AssertionError("unreachable")


def _paginate(
    client: Any,
    method_name: str,
    operation: str,
    region: str | None,
    sleep: Sleep,
    result_key: str,
    **kwargs: Any,
) -> dict[str, Any]:
    for attempt in range(4):
        combined: list[Any] = []
        try:
            paginator = client.get_paginator(method_name)
            for page in paginator.paginate(**kwargs):
                combined.extend(page.get(result_key, []))
            return {result_key: combined}
        except Exception as exc:
            code, _ = client_error_code(exc)
            if code in THROTTLING_CODES and attempt < 3:
                sleep(min(0.5 * (2**attempt), 8.0))
                continue
            translate_client_error(exc, operation, region)
    raise AssertionError("unreachable")


def _paginate_manually(
    client: Any,
    method_name: str,
    operation: str,
    region: str | None,
    sleep: Sleep,
    result_key: str,
    **kwargs: Any,
) -> dict[str, Any]:
    combined: list[Any] = []
    token: str | None = None
    while True:
        request = dict(kwargs)
        if token is not None:
            request["NextToken"] = token
        page = _invoke(client, method_name, operation, region, sleep, **request)
        combined.extend(page.get(result_key, []))
        token = page.get("NextToken")
        if not token:
            return {result_key: combined}


class ReadOnlyEc2:
    def __init__(self, client: Any, sleep: Sleep = time.sleep) -> None:
        self.__client = client
        self.__sleep = sleep
        self.__region = getattr(client.meta, "region_name", None)

    def describe_regions(self) -> dict[str, Any]:
        return _invoke(
            self.__client,
            "describe_regions",
            "ec2:DescribeRegions",
            self.__region,
            self.__sleep,
        )

    def describe_volumes(self) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "describe_volumes",
            "ec2:DescribeVolumes",
            self.__region,
            self.__sleep,
            "Volumes",
        )

    def describe_addresses(self) -> dict[str, Any]:
        return _invoke(
            self.__client,
            "describe_addresses",
            "ec2:DescribeAddresses",
            self.__region,
            self.__sleep,
        )

    def describe_instances(self) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "describe_instances",
            "ec2:DescribeInstances",
            self.__region,
            self.__sleep,
            "Reservations",
        )

    def describe_snapshots(self) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "describe_snapshots",
            "ec2:DescribeSnapshots",
            self.__region,
            self.__sleep,
            "Snapshots",
            OwnerIds=["self"],
        )

    def describe_images(self) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "describe_images",
            "ec2:DescribeImages",
            self.__region,
            self.__sleep,
            "Images",
            Owners=["self"],
        )

    def describe_snapshot_attribute(self, snapshot_id: str) -> dict[str, Any]:
        return _invoke(
            self.__client,
            "describe_snapshot_attribute",
            "ec2:DescribeSnapshotAttribute",
            self.__region,
            self.__sleep,
            SnapshotId=snapshot_id,
            Attribute="createVolumePermission",
        )

    def describe_locked_snapshots(self, snapshot_ids: list[str]) -> dict[str, Any]:
        return _paginate_manually(
            self.__client,
            "describe_locked_snapshots",
            "ec2:DescribeLockedSnapshots",
            self.__region,
            self.__sleep,
            "Snapshots",
            SnapshotIds=snapshot_ids,
        )


class ReadOnlySts:
    def __init__(self, client: Any, sleep: Sleep = time.sleep) -> None:
        self.__client = client
        self.__sleep = sleep
        self.__region = getattr(client.meta, "region_name", None)

    def get_caller_identity(self) -> dict[str, Any]:
        return _invoke(
            self.__client,
            "get_caller_identity",
            "sts:GetCallerIdentity",
            self.__region,
            self.__sleep,
        )


class ReadOnlyPricing:
    def __init__(self, client: Any, sleep: Sleep = time.sleep) -> None:
        self.__client = client
        self.__sleep = sleep
        self.__region = getattr(client.meta, "region_name", None)

    def get_products(self, service_code: str, filters: list[dict[str, str]]) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "get_products",
            "pricing:GetProducts",
            self.__region,
            self.__sleep,
            "PriceList",
            ServiceCode=service_code,
            Filters=filters,
        )


class ReadOnlyCloudFormation:
    def __init__(self, client: Any, sleep: Sleep = time.sleep) -> None:
        self.__client = client
        self.__sleep = sleep
        self.__region = getattr(client.meta, "region_name", None)

    def list_stacks(self) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "list_stacks",
            "cloudformation:ListStacks",
            self.__region,
            self.__sleep,
            "StackSummaries",
        )

    def list_stack_resources(self, stack_name: str) -> dict[str, Any]:
        return _paginate(
            self.__client,
            "list_stack_resources",
            "cloudformation:ListStackResources",
            self.__region,
            self.__sleep,
            "StackResourceSummaries",
            StackName=stack_name,
        )
