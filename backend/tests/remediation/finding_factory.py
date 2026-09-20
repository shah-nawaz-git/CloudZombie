from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.core.enums import (
    CostConfidence,
    DetectionConfidence,
    DetectorType,
    FindingStatus,
    OwnershipStatus,
    PersistenceState,
    RemediationRisk,
    ResourceType,
)
from app.persistence.models import Finding

NOW = datetime(2026, 9, 20, 10, tzinfo=UTC)
SCAN_ID = UUID("11111111-1111-4111-8111-111111111111")


def make_finding(**changes) -> Finding:
    values = {
        "id": UUID("22222222-2222-4222-8222-222222222222"),
        "account_id": "123456789012",
        "region": "eu-central-1",
        "resource_type": ResourceType.EBS_VOLUME.value,
        "resource_id": "vol-0a1b2c3d4e5f60001",
        "detector_type": DetectorType.UNATTACHED_EBS_VOLUME.value,
        "title": "Volume review",
        "summary": "This volume is currently available with no attachments.",
        "resource_created_at": NOW - timedelta(days=180),
        "first_observed_at": NOW - timedelta(days=14),
        "last_observed_at": NOW,
        "streak_started_at": NOW - timedelta(days=14),
        "observation_count": 3,
        "consecutive_observations": 3,
        "persistence_state": PersistenceState.PERSISTENT.value,
        "detection_confidence": DetectionConfidence.HIGH.value,
        "remediation_risk": RemediationRisk.LOW.value,
        "cost_confidence": CostConfidence.MEDIUM.value,
        "estimated_monthly_cost": Decimal("47.60"),
        "cost_explanation": "Public list-price estimate.",
        "pricing_source": "fallback_table",
        "pricing_timestamp": NOW,
        "cost_line_items": [],
        "evidence": {},
        "known_dependencies": [],
        "ownership": {"status": OwnershipStatus.UNKNOWN.value, "notes": []},
        "related_resource_ids": [],
        "status": FindingStatus.OPEN.value,
        "resolved_at": None,
        "dismissed_at": None,
        "dismiss_reason": None,
        "ignore_reason": None,
        "first_scan_id": SCAN_ID,
        "last_scan_id": SCAN_ID,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return Finding(**values)
