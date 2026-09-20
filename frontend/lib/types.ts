export type Mode = "demo" | "live";
export type ScanStatus = "running" | "completed" | "partial" | "failed";
export type FindingStatus = "open" | "dismissed" | "resolved" | "ignored";
export type Risk = "LOW" | "REVIEW" | "HIGH";
export type Confidence = "HIGH" | "MEDIUM" | "LOW" | "UNAVAILABLE";

export interface Identity {
  mode: Mode;
  account_id: string | null;
  principal_arn: string | null;
  identity_type: string | null;
  verified_at: string | null;
  error: string | null;
}
export interface CoverageCell {
  status: string;
  error_code?: string | null;
  message?: string | null;
  missing_operation?: string | null;
}
export interface RegionCoverage {
  status: string;
  detectors: Record<string, CoverageCell>;
  warnings: string[];
}
export interface Scan {
  id: string;
  mode: Mode;
  account_id: string | null;
  principal_arn: string | null;
  seeded: boolean;
  started_at: string;
  finished_at: string | null;
  status: ScanStatus;
  requested_regions: string[];
  completed_regions: string[];
  partial_regions: string[];
  failed_regions: string[];
  skipped_regions: string[];
  coverage: Record<string, RegionCoverage>;
  new_findings: number;
  persistent_findings: number;
  resolved_findings: number;
  ignored_findings: number;
  estimated_exposure: number;
  potential_exposure_low_confidence: number;
  errors: Array<Record<string, unknown>>;
  created_at: string;
}
export interface ScanList {
  items: Scan[];
  total: number;
}
export interface Finding {
  id: string;
  account_id: string;
  region: string;
  resource_type: string;
  resource_id: string;
  detector_type: string;
  title: string;
  summary: string;
  resource_created_at: string | null;
  first_observed_at: string;
  last_observed_at: string;
  streak_started_at: string;
  observation_count: number;
  consecutive_observations: number;
  persistence_state: string;
  detection_confidence: Confidence;
  remediation_risk: Risk;
  cost_confidence: Confidence;
  estimated_monthly_cost: number | null;
  cost_explanation: string;
  pricing_source: string;
  pricing_timestamp: string | null;
  cost_line_items: Array<Record<string, unknown>>;
  evidence: Record<string, unknown>;
  known_dependencies: Array<{
    kind: string;
    target_id?: string | null;
    description: string;
    blocks_remediation: boolean;
  }>;
  ownership: {
    status: string;
    stack_name?: string | null;
    stack_id?: string | null;
    logical_id?: string | null;
    source?: string | null;
    terraform: string;
    notes: string[];
  };
  related_resource_ids: string[];
  status: FindingStatus;
  resolved_at: string | null;
  dismissed_at: string | null;
  dismiss_reason: string | null;
  ignore_reason: string | null;
  first_scan_id: string;
  last_scan_id: string;
  created_at: string;
  updated_at: string;
  resource_age_days: number | null;
  first_observed_days_ago: number;
  last_observed_days_ago: number;
  observation_age_days: number;
  days_until_persistent: number | null;
  threshold_days: number;
  script_kind: string;
  script_available: boolean;
  script_unavailable_reason: string | null;
}
export interface Observation {
  scan_id: string;
  observed_at: string;
  status: string;
  persistence_state: string;
  remediation_risk: Risk;
  estimated_monthly_cost: number | null;
}
export interface FindingDetail extends Finding {
  observations: Observation[];
  related_findings: Array<{
    id: string;
    resource_id: string;
    resource_type: string;
    status: string;
  }>;
}
export interface FindingList {
  items: Finding[];
  total: number;
  page: number;
  page_size: number;
}
export interface Plan {
  finding_id: string;
  resource_id: string;
  plain_language_summary: string;
  observation_history: {
    resource_created_at: string | null;
    first_observed_at: string;
    last_observed_at: string;
    observation_count: number;
    consecutive_observations: number;
    streak_started_at: string;
    persistence_state: string;
    threshold_days: number;
    days_until_persistent: number | null;
  };
  known_dependencies: Finding["known_dependencies"];
  ownership: Finding["ownership"];
  estimated_cost: {
    amount: string | null;
    confidence: Confidence;
    explanation: string;
    source: string;
    upper_bound: boolean;
  };
  preconditions: string[];
  warnings: string[];
  limitations: string[];
  recommended_action: string;
  script_available: boolean;
  script_kind: string;
  script_unavailable_reason: string | null;
}
export interface Script {
  kind: string;
  filename: string;
  content: string;
  checks: string[];
  warnings: string[];
  unavailable_reason: string | null;
  unavailable_text: string | null;
}
export interface HistoryPoint {
  scan_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  seeded: boolean;
  new_findings: number;
  resolved_findings: number;
  observed_findings: number;
  estimated_exposure: number;
  potential_exposure_low_confidence: number;
  observed_by_resource_type: Record<string, number>;
  exposure_by_resource_type: Record<string, number>;
}
export interface History {
  points: HistoryPoint[];
}
export interface Coverage {
  scan_id: string;
  started_at: string;
  status: string;
  regions: Record<string, RegionCoverage>;
  completed_regions: string[];
  partial_regions: string[];
  failed_regions: string[];
  skipped_regions: string[];
  errors: Array<Record<string, unknown>>;
}
export interface Overview {
  mode: Mode;
  account_id: string | null;
  latest_scan: Scan | null;
  scan_running: boolean;
  estimated_monthly_cleanup_opportunity: number;
  potential_low_confidence_exposure: number;
  open_findings: number;
  persistent_low_risk_candidates: number;
  review_required: number;
  high_risk: number;
  newly_observed: number;
  ignored: number;
  dismissed: number;
  resolved_in_latest_scan: number;
  regions_scanned: string[];
  coverage_summary: { complete: number; partial: number; failed: number; skipped: number };
  findings_by_resource_type: Record<string, number>;
  exposure_by_resource_type: Record<string, number>;
}
export interface SettingsData {
  regions: string[] | null;
  thresholds_days: Record<string, number>;
  min_consecutive_observations: number;
  ignore_tag_key: string;
  ignore_tag_value: string;
  ignore_reason_tag_key: string;
  pricing_mode: string;
  pricing_cache_ttl_seconds: number;
  max_region_concurrency: number;
  demo_anchor_at: string | null;
  mode: Mode;
  detector_thresholds_help: Record<string, string>;
}
