import re
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
    ScriptKind,
)
from app.models import AppSettings
from app.persistence.models import Finding
from app.remediation.plan import build_cleanup_plan

NOW = datetime(2026, 9, 20, 10, tzinfo=UTC)
SCAN_ID = UUID("11111111-1111-4111-8111-111111111111")


def finding(**changes) -> Finding:
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
        "evidence": {"state": "available"},
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


def test_persistent_low_plan_offers_guarded_script() -> None:
    plan = build_cleanup_plan(finding(), AppSettings(), NOW)
    assert plan.script_available is True
    assert plan.script_kind == ScriptKind.GUARDED_REMEDIATION
    assert plan.script_unavailable_reason is None
    assert "run the guarded script" in plan.recommended_action


def test_newly_observed_days_until_persistent() -> None:
    selected = finding(
        persistence_state=PersistenceState.NEWLY_OBSERVED.value,
        remediation_risk=RemediationRisk.REVIEW.value,
        streak_started_at=NOW - timedelta(days=2),
        last_observed_at=NOW,
    )
    plan = build_cleanup_plan(selected, AppSettings(), NOW)
    assert plan.observation_history.days_until_persistent == 5
    assert "5 days remaining" in plan.recommended_action


def test_reappeared_finding_mentions_current_streak() -> None:
    selected = finding(
        first_observed_at=NOW - timedelta(days=30),
        streak_started_at=NOW - timedelta(days=3),
        observation_count=5,
        consecutive_observations=2,
    )
    summary = build_cleanup_plan(selected, AppSettings(), NOW).plain_language_summary
    assert "previously resolved and re-observed" in summary
    assert "2 consecutive" in summary
    assert "current streak began" in summary


def test_cloudformation_confirmed_recommends_stack_change() -> None:
    selected = finding(
        remediation_risk=RemediationRisk.HIGH.value,
        ownership={
            "status": OwnershipStatus.CONFIRMED.value,
            "stack_name": "customer-api-prod",
            "notes": ["Change the stack."],
        },
    )
    plan = build_cleanup_plan(selected, AppSettings(), NOW)
    assert "CloudFormation stack customer-api-prod" in plan.recommended_action
    assert plan.script_available is False


def test_snapshot_with_ami_recommends_resolving_dependency() -> None:
    selected = finding(
        resource_type=ResourceType.EBS_SNAPSHOT.value,
        resource_id="snap-0a1b2c3d4e5f60001",
        detector_type=DetectorType.SNAPSHOT_MISSING_SOURCE_VOLUME.value,
        remediation_risk=RemediationRisk.HIGH.value,
        known_dependencies=[
            {
                "kind": "registered_ami",
                "target_id": "ami-0a1b2c3d4e5f60001",
                "description": "Referenced by registered AMI ami-0a1b2c3d4e5f60001",
                "blocks_remediation": True,
            }
        ],
        cost_confidence=CostConfidence.LOW.value,
    )
    plan = build_cleanup_plan(selected, AppSettings(), NOW)
    assert "Resolve the blocking dependency first" in plan.recommended_action
    assert "registered AMI" in plan.recommended_action
    assert any("incremental" in item for item in plan.limitations)


def test_dismissed_is_not_available() -> None:
    plan = build_cleanup_plan(finding(status=FindingStatus.DISMISSED.value), AppSettings(), NOW)
    assert plan.script_available is False
    assert plan.recommended_action == "No action: finding is dismissed."


def test_plan_language_keeps_resource_age_separate_from_observation_age() -> None:
    plan = build_cleanup_plan(finding(), AppSettings(), NOW)
    payload = plan.model_dump_json()
    assert (
        re.search(
            r"(?i)(unattached|unassociated|stopped|unused|idle|orphan)\w* for \d+ days",
            payload,
        )
        is None
    )
    assert "orphan" not in payload.lower()
    assert "guaranteed savings" not in payload.lower()
    assert plan.observation_history.resource_created_at == NOW - timedelta(days=180)
    assert plan.observation_history.first_observed_at == NOW - timedelta(days=14)
    assert "resource age is not evidence" in plan.plain_language_summary
