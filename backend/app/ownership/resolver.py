from app.models import FindingCandidate, Ownership
from app.providers.base import CloudProvider


class OwnershipResolver:
    def __init__(self, provider: CloudProvider, region: str) -> None:
        self._provider = provider
        self._region = region

    def resolve(self, candidate: FindingCandidate) -> Ownership:
        return Ownership(notes=["CloudFormation ownership not evaluated yet"])
