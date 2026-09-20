import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import (
    CostConfidence,
    DetectorCoverageStatus,
    DetectorType,
    FindingStatus,
    RegionCoverageStatus,
    ScanStatus,
)
from app.detectors.base import ScanContext
from app.detectors.registry import DETECTORS
from app.models import AppSettings, CoverageCell, FindingCandidate, RegionCoverage
from app.ownership.resolver import OwnershipResolver
from app.persistence.models import Finding, Scan
from app.pricing.service import PricingService
from app.providers.base import CloudProvider, Identity
from app.providers.errors import (
    ProviderCredentialsError,
    ProviderError,
    ProviderPermissionError,
    ProviderRegionUnavailableError,
)
from app.providers.memoizing import ScanScopedProvider
from app.scanner.history import reconcile

SessionFactory = Callable[[], Session]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectionCell:
    detector_type: DetectorType
    status: DetectorCoverageStatus
    candidates: list[FindingCandidate]
    error: dict[str, str] | None = None


@dataclass(frozen=True)
class RegionDetection:
    region: str
    status: RegionCoverageStatus
    cells: list[DetectionCell]
    warnings: list[str]


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


class ScanEngine:
    def __init__(
        self,
        provider: CloudProvider,
        session_factory: SessionFactory,
        settings_service: AppSettings,
        pricing: PricingService,
        clock: Clock,
    ) -> None:
        self._provider = provider
        self._session_factory = session_factory
        self._settings = settings_service
        self._pricing = pricing
        self._clock = clock

    def _detect_region(
        self,
        provider: CloudProvider,
        identity: Identity,
        region: str,
        observed_at: datetime,
    ) -> RegionDetection:
        cells: list[DetectionCell] = []
        warnings: list[str] = []
        resolver = OwnershipResolver(provider, region)
        for detector in DETECTORS:
            try:
                context = ScanContext(identity.account_id, region, observed_at, self._settings)
                enriched: list[FindingCandidate] = []
                for candidate in detector.scan(provider, region, context):
                    ownership = resolver.resolve(candidate)
                    pricing_result = (
                        self._pricing.estimate(candidate.pricing_request)
                        if candidate.pricing_request is not None
                        else None
                    )
                    warnings.extend(candidate.warnings)
                    if pricing_result is not None:
                        warnings.extend(pricing_result.warnings)
                    enriched.append(
                        candidate.model_copy(
                            update={"ownership": ownership, "pricing_result": pricing_result}
                        )
                    )
                cells.append(
                    DetectionCell(detector.detector_type, DetectorCoverageStatus.COMPLETE, enriched)
                )
            except ProviderPermissionError as exc:
                error = {
                    "code": "permission_denied",
                    "message": str(exc),
                    "missing_operation": exc.operation,
                }
                cells.append(
                    DetectionCell(
                        detector.detector_type,
                        DetectorCoverageStatus.MISSING_PERMISSION,
                        [],
                        error,
                    )
                )
            except ProviderRegionUnavailableError as exc:
                error = {"code": "region_unavailable", "message": str(exc)}
                cells.append(
                    DetectionCell(detector.detector_type, DetectorCoverageStatus.SKIPPED, [], error)
                )
                return RegionDetection(
                    region, RegionCoverageStatus.SKIPPED, cells, _deduplicate(warnings)
                )
            except ProviderError as exc:
                error = {"code": "provider_error", "message": str(exc)}
                cells.append(
                    DetectionCell(detector.detector_type, DetectorCoverageStatus.FAILED, [], error)
                )
            except Exception as exc:
                logger.exception(
                    "Detector %s failed unexpectedly in %s",
                    detector.detector_type.value,
                    region,
                )
                error = {
                    "code": "internal_error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
                cells.append(
                    DetectionCell(detector.detector_type, DetectorCoverageStatus.FAILED, [], error)
                )
        if resolver.warning is not None:
            warnings.append(resolver.warning)
        statuses = {cell.status for cell in cells}
        if statuses == {DetectorCoverageStatus.COMPLETE}:
            status = RegionCoverageStatus.COMPLETE
        elif (
            DetectorCoverageStatus.COMPLETE in statuses
            or DetectorCoverageStatus.MISSING_PERMISSION in statuses
        ):
            status = RegionCoverageStatus.PARTIAL
        else:
            status = RegionCoverageStatus.FAILED
        return RegionDetection(region, status, cells, _deduplicate(warnings))

    def run_scan(
        self,
        requested_regions: list[str] | None = None,
        *,
        scan_id: UUID | None = None,
    ) -> Scan:
        provider = ScanScopedProvider(self._provider)
        with self._session_factory() as session:
            scan: Scan
            if scan_id is None:
                observed_at = self._clock.now()
                scan = Scan(
                    mode=provider.mode.value,
                    account_id=None,
                    principal_arn=None,
                    seeded=False,
                    started_at=observed_at,
                    status=ScanStatus.RUNNING.value,
                    requested_regions=requested_regions or [],
                    completed_regions=[],
                    partial_regions=[],
                    failed_regions=[],
                    skipped_regions=[],
                    coverage={},
                    errors=[],
                    created_at=observed_at,
                )
                session.add(scan)
                session.flush()
            else:
                existing_scan = session.get(Scan, scan_id)
                if existing_scan is None or existing_scan.status != ScanStatus.RUNNING.value:
                    raise ValueError("scan_id must identify an existing running scan")
                scan = existing_scan
                observed_at = scan.started_at
            try:
                identity = provider.get_identity()
            except ProviderCredentialsError as exc:
                scan.status = ScanStatus.FAILED.value
                scan.finished_at = self._clock.now()
                scan.errors = [{"scope": "scan", "code": "credentials_error", "message": str(exc)}]
                session.commit()
                return scan

            scan.account_id = identity.account_id
            scan.principal_arn = identity.principal_arn
            try:
                region_info = {item.name: item for item in provider.list_regions()}
            except ProviderError as exc:
                scan.status = ScanStatus.FAILED.value
                scan.finished_at = self._clock.now()
                scan.errors = [
                    {"scope": "scan", "code": "region_discovery_error", "message": str(exc)}
                ]
                session.commit()
                return scan

            if requested_regions is not None:
                regions = list(dict.fromkeys(requested_regions))
            elif scan_id is not None and scan.requested_regions:
                regions = list(scan.requested_regions)
            elif self._settings.regions is not None:
                regions = self._settings.regions
            else:
                regions = list(region_info)
            scan.requested_regions = list(regions)

            detection_by_region: dict[str, RegionDetection] = {}
            runnable: list[str] = []
            for region in regions:
                info = region_info.get(region)
                if info is not None and info.opt_in_status == "not-opted-in":
                    detection_by_region[region] = RegionDetection(
                        region,
                        RegionCoverageStatus.SKIPPED,
                        [],
                        ["region not enabled (opt-in required)"],
                    )
                else:
                    runnable.append(region)
            with ThreadPoolExecutor(max_workers=self._settings.max_region_concurrency) as executor:
                results = executor.map(
                    lambda selected: self._detect_region(provider, identity, selected, observed_at),
                    runnable,
                )
                detection_by_region.update({result.region: result for result in results})
            detections = [detection_by_region[region] for region in regions]

            coverage: dict[str, dict] = {}
            errors: list[dict[str, str]] = []
            observed_findings: list[Finding] = []
            completed: list[str] = []
            partial: list[str] = []
            failed: list[str] = []
            skipped: list[str] = []
            for result in detections:
                region_coverage = RegionCoverage(
                    status=result.status,
                    detectors={
                        cell.detector_type: CoverageCell(
                            status=cell.status,
                            error_code=cell.error.get("code") if cell.error else None,
                            message=cell.error.get("message") if cell.error else None,
                            missing_operation=(
                                cell.error.get("missing_operation") if cell.error else None
                            ),
                        )
                        for cell in result.cells
                    },
                    warnings=result.warnings,
                )
                coverage[result.region] = region_coverage.model_dump(mode="json")
                if result.status == RegionCoverageStatus.COMPLETE:
                    completed.append(result.region)
                elif result.status == RegionCoverageStatus.PARTIAL:
                    partial.append(result.region)
                elif result.status == RegionCoverageStatus.FAILED:
                    failed.append(result.region)
                else:
                    skipped.append(result.region)
                for cell in result.cells:
                    if cell.error:
                        errors.append(
                            {
                                "scope": "detector",
                                "region": result.region,
                                "detector_type": cell.detector_type.value,
                                **cell.error,
                            }
                        )
                    reconciled = reconcile(
                        session,
                        scan,
                        result.region,
                        cell.detector_type,
                        cell.candidates,
                        cell.status,
                        self._settings,
                        observed_at,
                    )
                    scan.new_findings += reconciled.new
                    scan.persistent_findings += reconciled.persistent
                    scan.resolved_findings += reconciled.resolved
                    scan.ignored_findings += reconciled.ignored
                    observed_findings.extend(reconciled.observed_findings)

            headline = Decimal("0")
            low_confidence = Decimal("0")
            for finding in observed_findings:
                if (
                    finding.status == FindingStatus.OPEN.value
                    and finding.estimated_monthly_cost is not None
                ):
                    if finding.cost_confidence in {
                        CostConfidence.HIGH.value,
                        CostConfidence.MEDIUM.value,
                    }:
                        headline += finding.estimated_monthly_cost
                    elif finding.cost_confidence == CostConfidence.LOW.value:
                        low_confidence += finding.estimated_monthly_cost
            scan.completed_regions = completed
            scan.partial_regions = partial
            scan.failed_regions = failed
            scan.skipped_regions = skipped
            scan.estimated_exposure = headline
            scan.potential_exposure_low_confidence = low_confidence
            scan.coverage = coverage
            scan.errors = errors
            if not runnable:
                scan.status = ScanStatus.FAILED.value
            elif partial or failed:
                scan.status = ScanStatus.PARTIAL.value
            else:
                scan.status = ScanStatus.COMPLETED.value
            scan.finished_at = self._clock.now()
            session.commit()
            return scan
