from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_context, get_session
from app.api.errors import NotFoundError
from app.api.schemas import (
    DETECTOR_THRESHOLDS_HELP,
    BulkScriptIn,
    BulkScriptOut,
    CoverageOut,
    FindingDetailOut,
    FindingListOut,
    FindingOut,
    FindingPatchIn,
    HealthOut,
    HistoryOut,
    IdentityOut,
    ObservationOut,
    OverviewOut,
    PlanOut,
    RelatedFindingOut,
    ScanCreateIn,
    ScanListOut,
    ScanOut,
    ScriptOut,
    SettingsOut,
    SettingsPatchIn,
)
from app.core.enums import DetectorType, Mode, ScanStatus
from app.models import AppSettings
from app.persistence.models import Finding, Scan
from app.remediation.eligibility import SCRIPT_UNAVAILABLE_TEXT, script_kind_for
from app.remediation.plan import build_cleanup_plan
from app.services.app_context import AppContext
from app.services.finding_service import FindingService
from app.services.history_service import HistoryService
from app.services.overview_service import OverviewService
from app.services.script_service import ScriptService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api")
SessionDep = Annotated[Session, Depends(get_session)]
ContextDep = Annotated[AppContext, Depends(get_context)]


def _days(start: datetime, end: datetime) -> int:
    return max((end.astimezone(UTC) - start.astimezone(UTC)).days, 0)


def scan_out(scan: Scan) -> ScanOut:
    return ScanOut.model_validate(scan)


def finding_out(finding: Finding, settings: AppSettings, now: datetime) -> FindingOut:
    threshold = settings.thresholds_days[DetectorType(finding.detector_type)]
    observation_age = (finding.last_observed_at - finding.streak_started_at).days
    persistent = finding.persistence_state == "persistent"
    kind, reason = script_kind_for(finding)
    data = {column.name: getattr(finding, column.name) for column in Finding.__table__.columns}
    data.update(
        {
            "resource_age_days": (
                _days(finding.resource_created_at, now) if finding.resource_created_at else None
            ),
            "first_observed_days_ago": _days(finding.first_observed_at, now),
            "last_observed_days_ago": _days(finding.last_observed_at, now),
            "observation_age_days": observation_age,
            "days_until_persistent": (None if persistent else max(threshold - observation_age, 0)),
            "threshold_days": threshold,
            "script_kind": kind,
            "script_available": reason is None,
            "script_unavailable_reason": reason,
        }
    )
    return FindingOut.model_validate(data)


def script_out(finding: Finding, context: AppContext, settings: AppSettings) -> ScriptOut:
    kind, reason = script_kind_for(finding)
    generated = ScriptService(settings, context.clock).for_finding(finding)
    return ScriptOut(
        kind=generated.kind,
        filename=generated.filename,
        content=generated.content,
        checks=generated.checks,
        warnings=generated.warnings,
        unavailable_reason=reason,
        unavailable_text=SCRIPT_UNAVAILABLE_TEXT[reason] if reason else None,
    )


@router.get("/health", response_model=HealthOut)
def health(session: SessionDep, context: ContextDep) -> HealthOut:
    session.execute(text("SELECT 1"))
    database = "sqlite" if context.env.database_url.startswith("sqlite") else "postgresql"
    return HealthOut(
        status="ok",
        mode=context.env.cloudzombie_mode.value,
        database=database,
        version=context.version,
    )


@router.get("/identity", response_model=IdentityOut)
def identity(context: ContextDep, refresh: bool = False) -> IdentityOut:
    if refresh:
        context.identity_status.refresh(context.provider, context.clock)
    status = context.identity_status
    return IdentityOut(
        mode=status.mode,
        account_id=status.account_id,
        principal_arn=status.principal_arn,
        identity_type=status.identity_type,
        verified_at=status.verified_at,
        error=status.error,
    )


@router.post("/scans", response_model=ScanOut, status_code=202)
def create_scan(body: ScanCreateIn, context: ContextDep) -> ScanOut:
    assert context.scan_runner is not None
    return scan_out(context.scan_runner.start(body.regions, body.wait))


@router.get("/scans", response_model=ScanListOut)
def list_scans(session: SessionDep, limit: int = Query(50, ge=1, le=200)) -> ScanListOut:
    total = session.scalar(select(func.count()).select_from(Scan)) or 0
    scans = list(session.scalars(select(Scan).order_by(Scan.started_at.desc()).limit(limit)))
    return ScanListOut(items=[scan_out(item) for item in scans], total=total)


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: UUID, session: SessionDep) -> ScanOut:
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise NotFoundError(f"Scan {scan_id} was not found.")
    return scan_out(scan)


@router.get("/findings", response_model=FindingListOut)
def list_findings(
    session: SessionDep,
    context: ContextDep,
    resource_type: str | None = None,
    region: str | None = None,
    status: Annotated[list[str] | None, Query()] = None,
    detection_confidence: str | None = None,
    remediation_risk: str | None = None,
    cost_confidence: str | None = None,
    ownership: str | None = None,
    persistence_state: str | None = None,
    first_observed_before: datetime | None = None,
    first_observed_after: datetime | None = None,
    min_observation_count: int | None = Query(None, ge=1),
    q: str | None = None,
    sort: Literal[
        "estimated_monthly_cost",
        "resource_created_at",
        "first_observed_at",
        "last_observed_at",
        "observation_count",
        "detection_confidence",
        "remediation_risk",
        "region",
        "resource_id",
    ] = "estimated_monthly_cost",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> FindingListOut:
    settings = SettingsService(session, context.env).load()
    result = FindingService(session).list_findings(
        resource_type=resource_type,
        region=region,
        statuses=status,
        detection_confidence=detection_confidence,
        remediation_risk=remediation_risk,
        cost_confidence=cost_confidence,
        ownership=ownership,
        persistence_state=persistence_state,
        first_observed_before=first_observed_before,
        first_observed_after=first_observed_after,
        min_observation_count=min_observation_count,
        q=q,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return FindingListOut(
        items=[finding_out(item, settings, context.clock.now()) for item in result.items],
        total=result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/findings/{finding_id}", response_model=FindingDetailOut)
def get_finding(finding_id: UUID, session: SessionDep, context: ContextDep) -> FindingDetailOut:
    service = FindingService(session)
    finding = service.get(finding_id)
    settings = SettingsService(session, context.env).load()
    base = finding_out(finding, settings, context.clock.now()).model_dump()
    observations = [
        ObservationOut(
            scan_id=item.scan_id,
            observed_at=item.observed_at,
            status=item.status_at_observation,
            persistence_state=item.persistence_state_at_observation,
            remediation_risk=item.remediation_risk_at_observation,
            estimated_monthly_cost=(
                float(item.estimated_monthly_cost)
                if item.estimated_monthly_cost is not None
                else None
            ),
        )
        for item in service.observations(finding.id)
    ]
    related = [RelatedFindingOut.model_validate(item) for item in service.related(finding)]
    return FindingDetailOut(**base, observations=observations, related_findings=related)


@router.patch("/findings/{finding_id}", response_model=FindingOut)
def patch_finding(
    finding_id: UUID,
    body: FindingPatchIn,
    session: SessionDep,
    context: ContextDep,
) -> FindingOut:
    finding = FindingService(session).patch(
        finding_id, body.status, body.reason, context.clock.now()
    )
    settings = SettingsService(session, context.env).load()
    return finding_out(finding, settings, context.clock.now())


@router.get("/findings/{finding_id}/plan", response_model=PlanOut)
def get_plan(finding_id: UUID, session: SessionDep, context: ContextDep) -> PlanOut:
    finding = FindingService(session).get(finding_id)
    settings = SettingsService(session, context.env).load()
    return build_cleanup_plan(finding, settings, context.clock.now())


@router.get("/findings/{finding_id}/script", response_model=ScriptOut)
def get_script(
    finding_id: UUID,
    session: SessionDep,
    context: ContextDep,
    format: Literal["json", "raw"] = "json",
) -> Any:
    finding = FindingService(session).get(finding_id)
    settings = SettingsService(session, context.env).load()
    output = script_out(finding, context, settings)
    if format == "raw":
        return PlainTextResponse(
            output.content,
            media_type="text/x-shellscript",
            headers={"Content-Disposition": f'attachment; filename="{output.filename}"'},
        )
    return output


@router.post("/scripts/bulk", response_model=BulkScriptOut)
def bulk_script(body: BulkScriptIn, session: SessionDep, context: ContextDep) -> BulkScriptOut:
    findings = [FindingService(session).get(finding_id) for finding_id in body.finding_ids]
    settings = SettingsService(session, context.env).load()
    result = ScriptService(settings, context.clock).bulk(findings)
    output = None
    if result.script:
        output = ScriptOut(
            kind=result.script.kind,
            filename=result.script.filename,
            content=result.script.content,
            checks=result.script.checks,
            warnings=result.script.warnings,
        )
    return BulkScriptOut(script=output, included=result.included, skipped=result.skipped)


@router.get("/history", response_model=HistoryOut)
def history(session: SessionDep, limit: int = Query(50, ge=1, le=200)) -> HistoryOut:
    return HistoryOut(points=HistoryService(session).points(limit))


@router.get("/coverage", response_model=CoverageOut)
def coverage(session: SessionDep) -> CoverageOut:
    scan = session.scalar(
        select(Scan)
        .where(Scan.status != ScanStatus.RUNNING.value)
        .order_by(Scan.started_at.desc())
        .limit(1)
    )
    if scan is None:
        raise NotFoundError("No completed scan coverage is available.")
    return CoverageOut(
        scan_id=scan.id,
        started_at=scan.started_at,
        status=scan.status,
        regions=scan.coverage,
        completed_regions=scan.completed_regions,
        partial_regions=scan.partial_regions,
        failed_regions=scan.failed_regions,
        skipped_regions=scan.skipped_regions,
        errors=scan.errors,
    )


@router.get("/overview", response_model=OverviewOut)
def overview(session: SessionDep, context: ContextDep) -> OverviewOut:
    assert context.scan_runner is not None
    data = OverviewService(session).build(
        context.env.cloudzombie_mode.value,
        context.identity_status.account_id,
        context.scan_runner.is_running,
    )
    if data["latest_scan"] is not None:
        data["latest_scan"] = scan_out(data["latest_scan"])
    return OverviewOut.model_validate(data)


@router.get("/settings", response_model=SettingsOut)
def get_settings_endpoint(session: SessionDep, context: ContextDep) -> SettingsOut:
    settings = SettingsService(session, context.env).load()
    return SettingsOut(
        **settings.model_dump(),
        mode=context.env.cloudzombie_mode.value,
        detector_thresholds_help=DETECTOR_THRESHOLDS_HELP,
    )


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(body: SettingsPatchIn, session: SessionDep, context: ContextDep) -> SettingsOut:
    service = SettingsService(session, context.env)
    current = service.load()
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "thresholds_days" in changes:
        merged = {key.value: value for key, value in current.thresholds_days.items()}
        merged.update(changes["thresholds_days"])
        changes["thresholds_days"] = merged
    updated = AppSettings.model_validate({**current.model_dump(), **changes})
    if context.env.cloudzombie_mode == Mode.DEMO:
        updated.pricing_mode = "fallback_only"
    service.save(updated)
    session.commit()
    return SettingsOut(
        **updated.model_dump(),
        mode=context.env.cloudzombie_mode.value,
        detector_thresholds_help=DETECTOR_THRESHOLDS_HELP,
    )
