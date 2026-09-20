import type { Finding } from "@/lib/types";
import { isoDate, money, relativeDays, upperBound } from "@/lib/format";
import { ConfidenceChip, OwnershipChip, RiskChip, StatusChip } from "../chips";
import { FindingTitle } from "../FindingTitle";
import { Mono } from "../Mono";
type FindingsTableProps = {
  findings: Finding[];
  selected: string[];
  setSelected: (ids: string[]) => void;
  sort: string;
  order: string;
  onSort: (field: string) => void;
};
const columns = [
  ["Resource", null],
  ["Type", null],
  ["Region", "region"],
  ["Resource Age", "resource_created_at"],
  ["First Observed", "first_observed_at"],
  ["Observations", "observation_count"],
  ["Estimated Cost", "estimated_monthly_cost"],
  ["Confidence", "detection_confidence"],
  ["Risk", "remediation_risk"],
  ["Ownership", null],
  ["Status", null],
] as const;
export function FindingsTable({
  findings,
  selected,
  setSelected,
  sort,
  order,
  onSort,
}: FindingsTableProps) {
  return (
    <div className="panel table-wrap">
      <table aria-label="Findings table">
        <caption>Findings</caption>
        <thead>
          <tr>
            <th aria-label="Select" />
            {columns.map(([label, field]) => (
              <th key={label}>
                {field ? (
                  <button className="sort-button" onClick={() => onSort(field)}>
                    {label} {sort === field ? (order === "asc" ? "▲" : "▼") : ""}
                  </button>
                ) : (
                  label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => (
            <tr key={finding.id}>
              <td>
                {finding.script_available && (
                  <input
                    aria-label={`Select ${finding.resource_id}`}
                    type="checkbox"
                    checked={selected.includes(finding.id)}
                    onChange={(event) =>
                      setSelected(
                        event.target.checked
                          ? [...selected, finding.id]
                          : selected.filter((id) => id !== finding.id),
                      )
                    }
                  />
                )}
              </td>
              <td>
                <FindingTitle finding={finding} />
              </td>
              <td>{finding.resource_type.replaceAll("_", " ")}</td>
              <td>
                <Mono>{finding.region}</Mono>
              </td>
              <td>
                {finding.resource_age_days == null ? (
                  <span title="AWS does not expose an allocation time">unknown</span>
                ) : (
                  `${finding.resource_age_days} days`
                )}
              </td>
              <td>
                {relativeDays(finding.first_observed_days_ago)}
                <br />
                <small>{isoDate(finding.first_observed_at)}</small>
              </td>
              <td>
                {finding.observation_count}
                {finding.consecutive_observations !== finding.observation_count && (
                  <small> ({finding.consecutive_observations} consecutive)</small>
                )}
              </td>
              <td
                title={
                  finding.estimated_monthly_cost == null ? "Cost estimate unavailable" : undefined
                }
              >
                {money(finding.estimated_monthly_cost, upperBound(finding))}
                <br />
                <ConfidenceChip value={finding.cost_confidence} />
              </td>
              <td>
                <ConfidenceChip value={finding.detection_confidence} />
              </td>
              <td>
                <RiskChip value={finding.remediation_risk} />
              </td>
              <td>
                <OwnershipChip value={finding.ownership.status} />
              </td>
              <td>
                <StatusChip value={finding.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
