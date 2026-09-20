from collections import Counter, defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import FindingStatus, PersistenceState, RemediationRisk
from app.persistence.models import Finding, Scan


class OverviewService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def build(self, mode: str, account_id: str | None, scan_running: bool) -> dict:
        latest = self._session.scalar(select(Scan).order_by(Scan.started_at.desc()).limit(1))
        findings = list(self._session.scalars(select(Finding)))
        open_findings = [item for item in findings if item.status == FindingStatus.OPEN.value]
        types = Counter(item.resource_type for item in open_findings)
        exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for finding in open_findings:
            if finding.estimated_monthly_cost is not None:
                exposure[finding.resource_type] += finding.estimated_monthly_cost
        coverage = Counter(
            entry.get("status") for entry in (latest.coverage.values() if latest else [])
        )
        return {
            "mode": mode,
            "account_id": account_id,
            "latest_scan": latest,
            "scan_running": scan_running,
            "estimated_monthly_cleanup_opportunity": float(
                latest.estimated_exposure if latest else 0
            ),
            "potential_low_confidence_exposure": float(
                latest.potential_exposure_low_confidence if latest else 0
            ),
            "open_findings": len(open_findings),
            "persistent_low_risk_candidates": sum(
                item.persistence_state == PersistenceState.PERSISTENT.value
                and item.remediation_risk == RemediationRisk.LOW.value
                for item in open_findings
            ),
            "review_required": sum(
                item.remediation_risk == RemediationRisk.REVIEW.value for item in open_findings
            ),
            "high_risk": sum(
                item.remediation_risk == RemediationRisk.HIGH.value for item in open_findings
            ),
            "newly_observed": sum(
                item.persistence_state == PersistenceState.NEWLY_OBSERVED.value
                for item in open_findings
            ),
            "ignored": sum(item.status == FindingStatus.IGNORED.value for item in findings),
            "dismissed": sum(item.status == FindingStatus.DISMISSED.value for item in findings),
            "resolved_in_latest_scan": latest.resolved_findings if latest else 0,
            "regions_scanned": latest.requested_regions if latest else [],
            "coverage_summary": {
                "complete": coverage.get("complete", 0),
                "partial": coverage.get("partial", 0),
                "failed": coverage.get("failed", 0),
                "skipped": coverage.get("skipped", 0),
            },
            "findings_by_resource_type": dict(types),
            "exposure_by_resource_type": {key: float(value) for key, value in exposure.items()},
        }
