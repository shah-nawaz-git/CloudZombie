from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.providers.demo import DemoProvider
from app.providers.errors import ProviderPermissionError

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


def test_demo_module_does_not_import_boto() -> None:
    source = (Path(__file__).parents[2] / "app" / "providers" / "demo.py").read_text(
        encoding="utf-8"
    )
    assert "import boto3" not in source
    assert "import botocore" not in source
