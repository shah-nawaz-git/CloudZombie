from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DetectorType, FindingStatus
from app.persistence.models import Finding, FindingObservation, Scan


def get_finding_by_identity(
    session: Session,
    account_id: str,
    region: str,
    resource_type: str,
    resource_id: str,
    detector_type: str,
) -> Finding | None:
    return session.scalar(
        select(Finding).where(
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.resource_type == resource_type,
            Finding.resource_id == resource_id,
            Finding.detector_type == detector_type,
        )
    )


def list_findings_for_cell(
    session: Session, account_id: str, region: str, detector_type: DetectorType | str
) -> list[Finding]:
    return list(
        session.scalars(
            select(Finding).where(
                Finding.account_id == account_id,
                Finding.region == region,
                Finding.detector_type == str(detector_type),
            )
        )
    )


def list_findings(session: Session) -> list[Finding]:
    return list(session.scalars(select(Finding).order_by(Finding.region, Finding.resource_id)))


def list_open_findings_observed_by_scan(session: Session, scan: Scan) -> list[Finding]:
    return list(
        session.scalars(
            select(Finding)
            .join(FindingObservation)
            .where(
                FindingObservation.scan_id == scan.id,
                Finding.status == FindingStatus.OPEN.value,
            )
        )
    )


def list_observations(session: Session, finding: Finding) -> Sequence[FindingObservation]:
    return session.scalars(
        select(FindingObservation)
        .where(FindingObservation.finding_id == finding.id)
        .order_by(FindingObservation.observed_at)
    ).all()
