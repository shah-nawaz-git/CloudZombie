import Link from "next/link";
import { formatTimestamp, money } from "@/lib/format";
import type { FindingDetail } from "@/lib/types";
import { Mono } from "../Mono";
export function ObservationTimeline({ finding }: { finding: FindingDetail }) {
  return (
    <section className="panel">
      <h2>Observation timeline</h2>
      <table aria-label="Observation timeline">
        <thead>
          <tr>
            <th>Scan date</th>
            <th>Status</th>
            <th>Persistence</th>
            <th>Risk</th>
            <th>Cost</th>
          </tr>
        </thead>
        <tbody>
          {finding.observations.map((observation) => (
            <tr key={observation.scan_id}>
              <td>{formatTimestamp(observation.observed_at)}</td>
              <td>{observation.status}</td>
              <td>{observation.persistence_state}</td>
              <td>{observation.remediation_risk}</td>
              <td>{money(observation.estimated_monthly_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {finding.related_findings.length > 0 && (
        <>
          <h3>Related findings</h3>
          {finding.related_findings.map((related) => (
            <Link key={related.id} href={`/findings/${related.id}`}>
              <Mono>{related.resource_id}</Mono>
            </Link>
          ))}
        </>
      )}
    </section>
  );
}
