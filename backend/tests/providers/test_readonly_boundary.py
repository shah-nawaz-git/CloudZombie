import inspect
import json
from pathlib import Path

from botocore.client import BaseClient

from app.providers.aws.guard import ALLOWED_OPERATIONS
from app.providers.aws.readonly import (
    ReadOnlyCloudFormation,
    ReadOnlyEc2,
    ReadOnlyPricing,
    ReadOnlySts,
)


class Meta:
    region_name = "us-east-1"


class FakeClient:
    meta = Meta()


EXPECTED = {
    ReadOnlyEc2: {
        "describe_regions",
        "describe_volumes",
        "describe_addresses",
        "describe_instances",
        "describe_snapshots",
        "describe_images",
        "describe_snapshot_attribute",
        "describe_locked_snapshots",
    },
    ReadOnlySts: {"get_caller_identity"},
    ReadOnlyPricing: {"get_products"},
    ReadOnlyCloudFormation: {"list_stacks", "list_stack_resources"},
}


def test_wrapper_public_surface_is_exact() -> None:
    for wrapper_type, expected in EXPECTED.items():
        wrapper = wrapper_type(FakeClient())
        public = {
            name
            for name, value in inspect.getmembers(wrapper, callable)
            if not name.startswith("_")
        }
        assert public == expected
        assert not hasattr(wrapper, "client")
        assert not hasattr(wrapper, "call")
        assert not hasattr(wrapper, "execute")
        assert not hasattr(wrapper, "meta")
        assert not any(
            isinstance(value, BaseClient)
            for name, value in inspect.getmembers(wrapper)
            if not name.startswith("_")
        )


def test_surface_operations_and_policy_equal_allowlist() -> None:
    operations = {
        "ec2:" + "".join(word.title() for word in method.split("_"))
        for method in EXPECTED[ReadOnlyEc2]
    }
    operations |= {
        "sts:GetCallerIdentity",
        "pricing:GetProducts",
        "cloudformation:ListStacks",
        "cloudformation:ListStackResources",
    }
    assert operations == ALLOWED_OPERATIONS
    policy_path = Path(__file__).parents[3] / "docs" / "iam-policy.json"
    actions = set(json.loads(policy_path.read_text(encoding="utf-8"))["Statement"][0]["Action"])
    assert actions == ALLOWED_OPERATIONS
    assert not any(action.startswith("cloudwatch:") for action in actions)
