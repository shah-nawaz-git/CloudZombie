from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.providers.demo import DemoDataset, DemoProvider, load_demo_dataset
from app.providers.errors import (
    ProviderPermissionError,
    ProviderThrottledError,
    ProviderTransientError,
)

ANCHOR = datetime(2026, 9, 20, tzinfo=UTC)


def provider(demo_dataset, step=5):
    return DemoProvider(demo_dataset, step, ANCHOR)


def test_step_filtering_and_created_at(demo_dataset) -> None:
    at_step_two = {item.volume_id for item in provider(demo_dataset, 2).list_volumes("us-east-1")}
    at_step_five = {item.volume_id for item in provider(demo_dataset).list_volumes("us-east-1")}
    assert "vol-0a1b2c3d4e5f60009" in at_step_two
    assert "vol-0a1b2c3d4e5f60009" not in at_step_five
    volume = next(
        item
        for item in provider(demo_dataset).list_volumes("us-east-1")
        if item.volume_id.endswith("0003")
    )
    assert volume.created_at == datetime(2026, 8, 6, tzinfo=UTC)


def test_fixture_relationships_and_regions(demo_dataset) -> None:
    demo = provider(demo_dataset)
    regions = {item.name: item.opt_in_status for item in demo.list_regions()}
    assert regions["me-south-1"] == "not-opted-in"
    attributes = demo.get_snapshot_attributes("eu-central-1", "snap-0a1b2c3d4e5f60003")
    assert attributes.shared_user_ids == ("210987654321",)
    images = demo.list_images("us-east-1")
    assert "snap-0a1b2c3d4e5f60002" in images[0].snapshot_ids
    stacks = demo.list_stack_resources("eu-central-1")
    assert any(
        item.physical_id == "vol-0a1b2c3d4e5f60002" and item.stack_name == "customer-api-prod"
        for item in stacks
    )


def test_snapshot_fault(demo_dataset) -> None:
    with pytest.raises(ProviderPermissionError) as caught:
        provider(demo_dataset).list_snapshots("ap-southeast-2")
    assert caught.value.operation == "ec2:DescribeSnapshots"


@pytest.mark.parametrize(
    ("method", "args", "operation"),
    [
        ("list_volumes", (), "ec2:DescribeVolumes"),
        ("list_addresses", (), "ec2:DescribeAddresses"),
        ("list_instances", (), "ec2:DescribeInstances"),
        ("list_snapshots", (), "ec2:DescribeSnapshots"),
        ("list_images", (), "ec2:DescribeImages"),
        ("get_snapshot_attributes", ("snap-1",), "ec2:DescribeSnapshotAttribute"),
        ("get_snapshot_locks", (["snap-1"],), "ec2:DescribeLockedSnapshots"),
        ("list_stack_resources", (), "cloudformation:ListStackResources"),
    ],
)
def test_all_demo_fault_operations_are_mapped(demo_dataset, method, args, operation) -> None:
    data = dict(demo_dataset.data)
    data["faults"] = [{"region": "us-east-1", "method": method, "kind": "access_denied"}]
    with pytest.raises(ProviderPermissionError) as caught:
        getattr(provider(DemoDataset(data)), method)("us-east-1", *args)
    assert caught.value.operation == operation


@pytest.mark.parametrize(
    ("kind", "error"),
    [("throttled", ProviderThrottledError), ("transient", ProviderTransientError)],
)
def test_demo_fault_kinds(demo_dataset, kind, error) -> None:
    data = dict(demo_dataset.data)
    data["faults"] = [{"region": "us-east-1", "method": "list_volumes", "kind": kind}]
    with pytest.raises(error):
        provider(DemoDataset(data)).list_volumes("us-east-1")


def test_explicit_fixture_path_precedes_environment(monkeypatch) -> None:
    fixture = Path(__file__).parents[3] / "fixtures" / "demo" / "dataset.json"
    monkeypatch.setenv("CLOUDZOMBIE_DEMO_FIXTURE", "missing.json")
    assert load_demo_dataset(fixture).data["account_id"] == "123456789012"


def test_demo_module_does_not_import_boto() -> None:
    source = (Path(__file__).parents[2] / "app" / "providers" / "demo.py").read_text(
        encoding="utf-8"
    )
    assert "import boto3" not in source
    assert "import botocore" not in source
