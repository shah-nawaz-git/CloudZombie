from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import CostConfidence, FindingStatus
from app.persistence.models import Finding, FindingObservation, Scan


class HistoryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def points(self, limit: int) -> list[dict]:
        scans = list(
            self._session.scalars(select(Scan).order_by(Scan.started_at.desc()).limit(limit))
        )
        points: list[dict] = []
        for scan in reversed(scans):
            rows = list(
                self._session.execute(
                    select(FindingObservation, Finding)
                    .join(Finding, Finding.id == FindingObservation.finding_id)
                    .where(FindingObservation.scan_id == scan.id)
                )
            )
            counts: dict[str, int] = defaultdict(int)
            exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for observation, finding in rows:
                counts[finding.resource_type] += 1
                if (
                    observation.status_at_observation == FindingStatus.OPEN.value
                    and observation.cost_confidence_at_observation
                    in {CostConfidence.HIGH.value, CostConfidence.MEDIUM.value}
                    and observation.estimated_monthly_cost is not None
                ):
                    exposure[finding.resource_type] += observation.estimated_monthly_cost
            points.append(
                {
                    "scan_id": scan.id,
                    "started_at": scan.started_at,
                    "finished_at": scan.finished_at,
                    "status": scan.status,
                    "seeded": scan.seeded,
                    "new_findings": scan.new_findings,
                    "resolved_findings": scan.resolved_findings,
                    "observed_findings": len(rows),
                    "estimated_exposure": float(scan.estimated_exposure),
                    "potential_exposure_low_confidence": float(
                        scan.potential_exposure_low_confidence
                    ),
                    "observed_by_resource_type": dict(counts),
                    "exposure_by_resource_type": {
                        key: float(value) for key, value in exposure.items()
                    },
                }
            )
        return points
