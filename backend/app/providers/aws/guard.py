from typing import Any

from app.providers.errors import OperationNotAllowedError

ALLOWED_OPERATIONS: frozenset[str] = frozenset(
    {
        "ec2:DescribeRegions",
        "ec2:DescribeVolumes",
        "ec2:DescribeAddresses",
        "ec2:DescribeInstances",
        "ec2:DescribeSnapshots",
        "ec2:DescribeImages",
        "ec2:DescribeSnapshotAttribute",
        "ec2:DescribeLockedSnapshots",
        "sts:GetCallerIdentity",
        "pricing:GetProducts",
        "cloudformation:ListStacks",
        "cloudformation:ListStackResources",
    }
)


def _operation_name(model: Any) -> str:
    service_model = model.service_model
    service = service_model.endpoint_prefix.lower()
    return f"{service}:{model.name}"


def _reject_disallowed(model: Any, **_: Any) -> None:
    operation = _operation_name(model)
    if operation not in ALLOWED_OPERATIONS:
        raise OperationNotAllowedError(operation)


def _register_guard(events: Any) -> None:
    events.register("provide-client-params.*.*", _reject_disallowed)
    events.register("before-call.*.*", _reject_disallowed)


def install_operation_guard(session: Any) -> None:
    if hasattr(session, "register"):
        _register_guard(session)
    elif hasattr(session, "events"):
        _register_guard(session.events)
    elif hasattr(session, "_session"):
        _register_guard(session._session)
    else:
        raise TypeError("unsupported AWS session type")


def guarded_client(session: Any, service: str, region: str | None = None) -> Any:
    if hasattr(session, "create_client"):
        client = session.create_client(service, region_name=region)
    else:
        client = session.client(service, region_name=region)
    _register_guard(client.meta.events)
    return client
