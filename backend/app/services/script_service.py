from dataclasses import dataclass
from uuid import UUID

from app.core.clock import Clock
from app.core.enums import DetectorType, ResourceType, ScriptKind
from app.models import AppSettings
from app.persistence.models import Finding
from app.remediation.eligibility import SCRIPT_UNAVAILABLE_TEXT, script_kind_for
from app.remediation.scripts.generator import (
    GeneratedScript,
    ScriptTarget,
    generate_bulk_script,
    generate_script,
)
from app.remediation.validators import (
    validate_account_id,
    validate_region,
    validate_resource_id,
    validate_scan_id,
    validate_tag_key,
    validate_tag_value,
)


@dataclass(frozen=True)
class BulkScriptResult:
    script: GeneratedScript | None
    included: list[UUID]
    skipped: list[dict[str, str]]


class ScriptService:
    def __init__(self, settings: AppSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    def _target(self, finding: Finding) -> ScriptTarget:
        resource_type = ResourceType(finding.resource_type)
        return ScriptTarget(
            region=validate_region(finding.region),
            resource_id=validate_resource_id(resource_type, finding.resource_id),
        )

    def for_finding(self, finding: Finding) -> GeneratedScript:
        kind, _ = script_kind_for(finding)
        return generate_script(
            kind=kind,
            detector_type=DetectorType(finding.detector_type),
            account_id=validate_account_id(finding.account_id),
            target=self._target(finding),
            scan_id=validate_scan_id(str(finding.last_scan_id)),
            generated_at=self._clock.now(),
            ignore_tag_key=validate_tag_key(self._settings.ignore_tag_key),
            ignore_tag_value=validate_tag_value(self._settings.ignore_tag_value),
        )

    def bulk(self, findings: list[Finding]) -> BulkScriptResult:
        included_findings: list[Finding] = []
        skipped: list[dict[str, str]] = []
        for finding in findings:
            kind, reason = script_kind_for(finding)
            if kind == ScriptKind.GUARDED_REMEDIATION and reason is None:
                included_findings.append(finding)
            else:
                skipped.append(
                    {
                        "finding_id": str(finding.id),
                        "reason": SCRIPT_UNAVAILABLE_TEXT[reason] if reason else "Not eligible.",
                    }
                )
        if not included_findings:
            return BulkScriptResult(None, [], skipped)
        account_id = validate_account_id(included_findings[0].account_id)
        targets = [
            (DetectorType(finding.detector_type), self._target(finding))
            for finding in included_findings
        ]
        script = generate_bulk_script(
            account_id=account_id,
            targets=targets,
            scan_id=validate_scan_id(str(included_findings[0].last_scan_id)),
            generated_at=self._clock.now(),
            ignore_tag_key=validate_tag_key(self._settings.ignore_tag_key),
            ignore_tag_value=validate_tag_value(self._settings.ignore_tag_value),
        )
        return BulkScriptResult(
            script,
            [finding.id for finding in included_findings],
            skipped,
        )
