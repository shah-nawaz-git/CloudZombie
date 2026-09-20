import botocore.session
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from app.providers.aws.readonly import ReadOnlyEc2
from app.providers.errors import (
    ProviderCredentialsError,
    ProviderPermissionError,
    ProviderRegionUnavailableError,
    ProviderThrottledError,
    ProviderTransientError,
)


def ec2_wrapper(sleep=lambda _: None):
    session = botocore.session.get_session()
    session.set_credentials("testing", "testing")
    client = session.create_client("ec2", region_name="us-east-1")
    return client, ReadOnlyEc2(client, sleep=sleep)


def test_describe_regions_requests_all_regions() -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_response("describe_regions", {"Regions": []}, {"AllRegions": True})
        assert wrapper.describe_regions() == {"Regions": []}


def test_two_page_volumes_and_snapshots() -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_volumes", {"Volumes": [{"VolumeId": "vol-1"}], "NextToken": "next"}, {}
        )
        stubber.add_response(
            "describe_volumes", {"Volumes": [{"VolumeId": "vol-2"}]}, {"NextToken": "next"}
        )
        result = wrapper.describe_volumes()
    assert [item["VolumeId"] for item in result["Volumes"]] == ["vol-1", "vol-2"]

    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_snapshots", {"Snapshots": [], "NextToken": "next"}, {"OwnerIds": ["self"]}
        )
        stubber.add_response(
            "describe_snapshots", {"Snapshots": []}, {"OwnerIds": ["self"], "NextToken": "next"}
        )
        assert wrapper.describe_snapshots() == {"Snapshots": []}


def test_locked_snapshots_next_token_loop() -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_locked_snapshots",
            {"Snapshots": [{"SnapshotId": "snap-1"}], "NextToken": "next"},
            {"SnapshotIds": ["snap-1"]},
        )
        stubber.add_response(
            "describe_locked_snapshots",
            {"Snapshots": [{"SnapshotId": "snap-2"}]},
            {"SnapshotIds": ["snap-1"], "NextToken": "next"},
        )
        result = wrapper.describe_locked_snapshots(["snap-1"])
    assert len(result["Snapshots"]) == 2


@pytest.mark.parametrize("code", ["AccessDenied", "UnauthorizedOperation"])
def test_permission_translation(code) -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_client_error("describe_volumes", code, "denied")
        with pytest.raises(ProviderPermissionError) as caught:
            wrapper.describe_volumes()
    assert caught.value.operation == "ec2:DescribeVolumes"


def test_throttling_retries_then_succeeds() -> None:
    delays = []
    client, wrapper = ec2_wrapper(delays.append)
    with Stubber(client) as stubber:
        for _ in range(3):
            stubber.add_client_error("describe_volumes", "Throttling", "slow")
        stubber.add_response("describe_volumes", {"Volumes": []})
        assert wrapper.describe_volumes() == {"Volumes": []}
    assert delays == [0.5, 1.0, 2.0]


def test_throttling_exhaustion() -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        for _ in range(4):
            stubber.add_client_error("describe_volumes", "Throttling", "slow")
        with pytest.raises(ProviderThrottledError):
            wrapper.describe_volumes()


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("ExpiredToken", ProviderCredentialsError),
        ("OptInRequired", ProviderRegionUnavailableError),
        ("InternalError", ProviderTransientError),
    ],
)
def test_error_translation(code, error) -> None:
    client, wrapper = ec2_wrapper()
    with Stubber(client) as stubber:
        stubber.add_client_error("describe_volumes", code, "failure")
        with pytest.raises(error):
            wrapper.describe_volumes()


def test_endpoint_connection_is_region_unavailable() -> None:
    class BrokenClient:
        class Meta:
            region_name = "us-east-1"

        meta = Meta()

        def get_paginator(self, method_name):
            return self

        def paginate(self, **kwargs):
            raise EndpointConnectionError(endpoint_url="https://ec2.invalid")

    with pytest.raises(ProviderRegionUnavailableError):
        ReadOnlyEc2(BrokenClient()).describe_volumes()
