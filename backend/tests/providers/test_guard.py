import botocore.session
import pytest
from botocore.stub import Stubber

from app.providers.aws.guard import guarded_client
from app.providers.aws.readonly import ReadOnlyPricing
from app.providers.errors import OperationNotAllowedError


def client(service, region="us-east-1"):
    session = botocore.session.get_session()
    session.set_credentials("testing", "testing")
    return guarded_client(session, service, region)


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("delete_volume", {"VolumeId": "vol-0a1b2c3d4e5f60001"}),
        ("terminate_instances", {"InstanceIds": ["i-0a1b2c3d4e5f60001"]}),
        ("release_address", {"AllocationId": "eipalloc-0a1b2c3d4e5f60001"}),
        (
            "create_tags",
            {"Resources": ["vol-0a1b2c3d4e5f60001"], "Tags": [{"Key": "x", "Value": "y"}]},
        ),
        ("modify_volume", {"VolumeId": "vol-0a1b2c3d4e5f60001", "Size": 10}),
    ],
)
def test_ec2_mutations_are_rejected_before_request(method, kwargs) -> None:
    ec2 = client("ec2")
    with Stubber(ec2), pytest.raises(OperationNotAllowedError):
        getattr(ec2, method)(**kwargs)


def test_allowed_describe_passes() -> None:
    ec2 = client("ec2")
    with Stubber(ec2) as stubber:
        stubber.add_response("describe_volumes", {"Volumes": []}, {})
        assert ec2.describe_volumes() == {"Volumes": []}
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize(
    ("service", "method", "kwargs"),
    [
        (
            "sts",
            "assume_role",
            {"RoleArn": "arn:aws:iam::123456789012:role/x", "RoleSessionName": "test"},
        ),
        ("cloudformation", "delete_stack", {"StackName": "x"}),
        ("pricing", "describe_services", {}),
    ],
)
def test_guard_applies_to_other_services(service, method, kwargs) -> None:
    aws_client = client(service, "us-east-1")
    with Stubber(aws_client), pytest.raises(OperationNotAllowedError):
        getattr(aws_client, method)(**kwargs)


def test_guard_allows_pricing_get_products_through_wrapper() -> None:
    pricing = client("pricing", "us-east-1")
    filters = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}]
    with Stubber(pricing) as stubber:
        stubber.add_response(
            "get_products",
            {"PriceList": ['{"product": {}}']},
            {"ServiceCode": "AmazonEC2", "Filters": filters},
        )
        result = ReadOnlyPricing(pricing).get_products("AmazonEC2", filters)
    assert result == {"PriceList": ['{"product": {}}']}
