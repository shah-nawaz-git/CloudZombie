from enum import StrEnum


class Mode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class ResourceType(StrEnum):
    EBS_VOLUME = "ebs_volume"
    ELASTIC_IP = "elastic_ip"
    EC2_INSTANCE = "ec2_instance"
    EBS_SNAPSHOT = "ebs_snapshot"


class DetectorType(StrEnum):
    UNATTACHED_EBS_VOLUME = "unattached_ebs_volume"
    UNASSOCIATED_ELASTIC_IP = "unassociated_elastic_ip"
    STOPPED_EC2_INSTANCE = "stopped_ec2_instance"
    SNAPSHOT_MISSING_SOURCE_VOLUME = "snapshot_missing_source_volume"


class FindingStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class PersistenceState(StrEnum):
    NEWLY_OBSERVED = "newly_observed"
    PERSISTENT = "persistent"


class DetectionConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RemediationRisk(StrEnum):
    LOW = "LOW"
    REVIEW = "REVIEW"
    HIGH = "HIGH"


class CostConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNAVAILABLE = "UNAVAILABLE"


class OwnershipStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    UNKNOWN = "UNKNOWN"


class ScanStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class RegionCoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class DetectorCoverageStatus(StrEnum):
    COMPLETE = "complete"
    MISSING_PERMISSION = "missing_permission"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScriptKind(StrEnum):
    GUARDED_REMEDIATION = "guarded_remediation"
    INVESTIGATION = "investigation"
