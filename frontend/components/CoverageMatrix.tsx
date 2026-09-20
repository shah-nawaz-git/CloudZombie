import type { Coverage, RegionCoverage } from "@/lib/types";
import { Mono } from "./Mono";
import { StatusChip } from "./chips";

const detectors = [
  ["unattached_ebs_volume", "Unattached EBS volumes"],
  ["unassociated_elastic_ip", "Unassociated Elastic IPs"],
  ["stopped_ec2_instance", "Stopped EC2 instances"],
  ["snapshot_missing_source_volume", "Snapshots with deleted source volume"],
] as const;

export function CoverageMatrix({
  coverage,
}: {
  coverage: Coverage | { regions: Record<string, RegionCoverage> };
}) {
  return (
    <div className="table-wrap">
      <table aria-label="Coverage matrix">
        <caption>Coverage matrix</caption>
        <thead>
          <tr>
            <th>Region</th>
            {detectors.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(coverage.regions).map(([region, data]) => (
            <tr key={region}>
              <td>
                <Mono>{region}</Mono>
              </td>
              {detectors.map(([key]) => {
                const cell = data.detectors[key];
                return (
                  <td key={key}>
                    {cell ? (
                      <>
                        <StatusChip value={cell.status} />
                        {cell.missing_operation && (
                          <div className="mono">{cell.missing_operation}</div>
                        )}
                      </>
                    ) : (
                      <StatusChip value={data.status} />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {Object.entries(coverage.regions).flatMap(([region, data]) =>
        data.warnings.map((warning) => (
          <div className="muted" key={`${region}-${warning}`}>
            {region}: {warning}
          </div>
        )),
      )}
    </div>
  );
}
