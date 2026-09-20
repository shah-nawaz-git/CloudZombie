import type { Finding } from "./types";
export const conditionWords: Record<string, string> = {
  unattached_ebs_volume: "unattached",
  unassociated_elastic_ip: "unassociated",
  stopped_ec2_instance: "stopped",
  snapshot_missing_source_volume: "without source volume",
};
export function money(value: number | null, upper = false) {
  return value == null ? "—" : `${upper ? "≤ " : ""}$${value.toFixed(2)}`;
}
export function isoDate(value: string) {
  return value.slice(0, 10);
}
export function relativeDays(days: number | null) {
  if (days == null) return "unknown";
  return days === 0 ? "today" : `${days} days ago`;
}
export function formatTimestamp(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 19)} UTC`;
}
export function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds} seconds ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  return `${Math.floor(hours / 24)} days ago`;
}
export function duration(start: string, end: string | null) {
  if (!end) return "—";
  return `${Math.max(0, (new Date(end).getTime() - new Date(start).getTime()) / 1000).toFixed(1)}s`;
}
export function upperBound(finding: Finding) {
  return finding.resource_type === "ebs_snapshot" && finding.cost_confidence === "LOW";
}
