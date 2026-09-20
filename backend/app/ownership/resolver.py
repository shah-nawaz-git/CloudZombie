from app.core.enums import OwnershipStatus
from app.models import FindingCandidate, Ownership
from app.providers.base import CloudProvider, StackResource
from app.providers.errors import ProviderError, ProviderPermissionError

_STACK_NAME_TAG = "aws:cloudformation:stack-name"
_STACK_ID_TAG = "aws:cloudformation:stack-id"
_LOGICAL_ID_TAG = "aws:cloudformation:logical-id"
_CLOUDFORMATION_TAGS = {_STACK_NAME_TAG, _STACK_ID_TAG, _LOGICAL_ID_TAG}


class OwnershipResolver:
    def __init__(self, provider: CloudProvider, region: str) -> None:
        self._provider = provider
        self._region = region
        self._loaded = False
        self._index_available = False
        self._index: dict[str, StackResource] = {}
        self._unavailable_reason: str | None = None
        self.warning: str | None = None

    def _load_index(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            resources = self._provider.list_stack_resources(self._region)
        except ProviderPermissionError as exc:
            self._unavailable_reason = f"missing {exc.operation}"
            self.warning = (
                f"CloudFormation ownership not evaluated in {self._region}: missing {exc.operation}"
            )
            return
        except ProviderError as exc:
            self._unavailable_reason = str(exc)
            self.warning = f"CloudFormation lookup failed in {self._region}: {exc}"
            return
        self._index_available = True
        self._index = {
            resource.physical_id: resource
            for resource in resources
            if resource.physical_id is not None
        }

    def resolve(self, candidate: FindingCandidate) -> Ownership:
        self._load_index()
        stack_resource = self._index.get(candidate.resource_id)
        if stack_resource is not None:
            return Ownership(
                status=OwnershipStatus.CONFIRMED,
                stack_name=stack_resource.stack_name,
                stack_id=stack_resource.stack_id,
                logical_id=stack_resource.logical_id,
                source="stack_resource_index",
                notes=[
                    f"Found as logical resource {stack_resource.logical_id} in stack "
                    f"{stack_resource.stack_name}.",
                    "Change the CloudFormation stack instead of deleting the resource manually.",
                ],
            )
        carries_tags = any(key in candidate.tags for key in _CLOUDFORMATION_TAGS)
        if carries_tags:
            note = (
                "Resource carries aws:cloudformation:* tags but is not in the current "
                "stack-resource index; the stack may have been deleted with a retained resource."
                if self._index_available
                else (
                    "Resource carries aws:cloudformation:* tags; the stack index could not "
                    "be queried."
                )
            )
            return Ownership(
                status=OwnershipStatus.LIKELY,
                stack_name=candidate.tags.get(_STACK_NAME_TAG),
                stack_id=candidate.tags.get(_STACK_ID_TAG),
                logical_id=candidate.tags.get(_LOGICAL_ID_TAG),
                source="tags",
                notes=[note],
            )
        if self._index_available:
            return Ownership(
                notes=[
                    f"Not found in any CloudFormation stack in {self._region}. UNKNOWN does "
                    "not mean unmanaged — Terraform, console or other tooling may own it."
                ]
            )
        reason = self._unavailable_reason or "stack index unavailable"
        return Ownership(
            notes=[
                f"CloudFormation ownership could not be evaluated: {reason}. UNKNOWN does "
                "not mean unmanaged."
            ]
        )
