from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.core.enums import DetectorType, ResourceType
from app.models import AppSettings, FindingCandidate
from app.providers.base import CloudProvider


@dataclass(frozen=True)
class ScanContext:
    account_id: str
    region: str
    observed_at: datetime
    settings: AppSettings


class Detector(ABC):
    detector_type: DetectorType
    resource_type: ResourceType
    required_operations: frozenset[str]

    @abstractmethod
    def scan(
        self, provider: CloudProvider, region: str, context: ScanContext
    ) -> list[FindingCandidate]: ...
