import type { HistoryPoint } from "./types";
export interface ChartPoint {
  label: string;
  ebs_volume: number;
  elastic_ip: number;
  ec2_instance: number;
  ebs_snapshot: number;
  estimated_exposure: number;
  potential_exposure_low_confidence: number;
}
export function historyChartData(points: HistoryPoint[]): ChartPoint[] {
  const days = new Set(points.map((point) => point.started_at.slice(0, 10)));
  const includeTime = days.size === 1 && points.length > 1;
  return points.map((point) => ({
    label: includeTime
      ? `${point.started_at.slice(5, 10)} ${point.started_at.slice(11, 16)}`
      : point.started_at.slice(5, 10),
    ebs_volume: point.observed_by_resource_type.ebs_volume || 0,
    elastic_ip: point.observed_by_resource_type.elastic_ip || 0,
    ec2_instance: point.observed_by_resource_type.ec2_instance || 0,
    ebs_snapshot: point.observed_by_resource_type.ebs_snapshot || 0,
    estimated_exposure: point.estimated_exposure,
    potential_exposure_low_confidence: point.potential_exposure_low_confidence,
  }));
}
