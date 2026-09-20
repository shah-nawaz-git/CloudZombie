from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.errors import InvalidTransitionError, NotFoundError
from app.core.enums import FindingStatus
from app.persistence.models import Finding, FindingObservation


@dataclass(frozen=True)
class FindingPage:
    items: list[Finding]
    total: int


_SORT_COLUMNS = {
    "estimated_monthly_cost": Finding.estimated_monthly_cost,
    "resource_created_at": Finding.resource_created_at,
    "first_observed_at": Finding.first_observed_at,
    "last_observed_at": Finding.last_observed_at,
    "observation_count": Finding.observation_count,
    "detection_confidence": Finding.detection_confidence,
    "remediation_risk": Finding.remediation_risk,
    "region": Finding.region,
    "resource_id": Finding.resource_id,
}


class FindingService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_findings(
        self,
        *,
        resource_type: str | None = None,
        region: str | None = None,
        statuses: list[str] | None = None,
        detection_confidence: str | None = None,
        remediation_risk: str | None = None,
        cost_confidence: str | None = None,
        ownership: str | None = None,
        persistence_state: str | None = None,
        first_observed_before: datetime | None = None,
        first_observed_after: datetime | None = None,
        min_observation_count: int | None = None,
        q: str | None = None,
        sort: str = "estimated_monthly_cost",
        order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> FindingPage:
        statement = select(Finding)
        if resource_type:
            statement = statement.where(Finding.resource_type == resource_type)
        if region:
            statement = statement.where(Finding.region == region)
        if statuses:
            statement = statement.where(Finding.status.in_(statuses))
        if detection_confidence:
            statement = statement.where(Finding.detection_confidence == detection_confidence)
        if remediation_risk:
            statement = statement.where(Finding.remediation_risk == remediation_risk)
        if cost_confidence:
            statement = statement.where(Finding.cost_confidence == cost_confidence)
        if persistence_state:
            statement = statement.where(Finding.persistence_state == persistence_state)
        if first_observed_before:
            statement = statement.where(Finding.first_observed_at <= first_observed_before)
        if first_observed_after:
            statement = statement.where(Finding.first_observed_at >= first_observed_after)
        if min_observation_count is not None:
            statement = statement.where(Finding.observation_count >= min_observation_count)
        if q:
            term = f"%{q}%"
            statement = statement.where(
                or_(Finding.resource_id.ilike(term), Finding.title.ilike(term))
            )
        findings = list(self._session.scalars(statement))
        if ownership:
            findings = [
                finding for finding in findings if finding.ownership.get("status") == ownership
            ]
        column = _SORT_COLUMNS[sort]
        ordered = sorted(
            findings,
            key=lambda item: (
                getattr(item, column.key) is None,
                getattr(item, column.key),
            ),
            reverse=order == "desc",
        )
        if order == "desc":
            non_null = [item for item in ordered if getattr(item, column.key) is not None]
            null = [item for item in ordered if getattr(item, column.key) is None]
            ordered = non_null + null
        total = len(ordered)
        start = (page - 1) * page_size
        return FindingPage(ordered[start : start + page_size], total)

    def get(self, finding_id: UUID) -> Finding:
        finding = self._session.get(Finding, finding_id)
        if finding is None:
            raise NotFoundError(f"Finding {finding_id} was not found.")
        return finding

    def observations(self, finding_id: UUID) -> list[FindingObservation]:
        return list(
            self._session.scalars(
                select(FindingObservation)
                .where(FindingObservation.finding_id == finding_id)
                .order_by(FindingObservation.observed_at)
            )
        )

    def related(self, finding: Finding) -> list[Finding]:
        if not finding.related_resource_ids:
            return []
        return list(
            self._session.scalars(
                select(Finding).where(Finding.resource_id.in_(finding.related_resource_ids))
            )
        )

    def patch(self, finding_id: UUID, status: str, reason: str | None, now: datetime) -> Finding:
        finding = self.get(finding_id)
        if finding.status == FindingStatus.OPEN.value and status == "dismissed":
            finding.status = FindingStatus.DISMISSED.value
            finding.dismissed_at = now
            finding.dismiss_reason = reason
        elif finding.status == FindingStatus.DISMISSED.value and status == "open":
            finding.status = FindingStatus.OPEN.value
            finding.dismissed_at = None
            finding.dismiss_reason = None
        else:
            raise InvalidTransitionError(
                f"Cannot transition finding from {finding.status} to {status}."
            )
        finding.updated_at = now
        self._session.commit()
        return finding
