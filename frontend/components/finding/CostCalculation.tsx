import { formatTimestamp, money } from "@/lib/format";
import type { FindingDetail } from "@/lib/types";
import { ConfidenceChip } from "../chips";
export function CostCalculation({ finding }: { finding: FindingDetail }) {
  const source =
    finding.pricing_source === "aws_pricing_api"
      ? "AWS Pricing API"
      : finding.pricing_source === "fallback_table"
        ? "Fallback list-price table"
        : "unavailable";
  return (
    <section className="panel">
      <h2>Cost calculation</h2>
      <strong>
        {money(finding.estimated_monthly_cost, finding.resource_type === "ebs_snapshot")}
      </strong>{" "}
      <ConfidenceChip label="Cost confidence" value={finding.cost_confidence} />
      <p>
        {source} · {formatTimestamp(finding.pricing_timestamp)}
      </p>
      {finding.resource_type === "ebs_snapshot" && (
        <p>Upper bound: snapshots are incremental and exact reclaimable storage is unknown.</p>
      )}
      <table aria-label="Cost line items">
        <thead>
          <tr>
            <th>Line item</th>
            <th>Quantity</th>
            <th>Unit price</th>
            <th>Monthly</th>
          </tr>
        </thead>
        <tbody>
          {finding.cost_line_items.map((line, index) => (
            <tr key={index}>
              <td>{String(line.label)}</td>
              <td>
                {String(line.quantity)} {String(line.unit)}
              </td>
              <td>${String(line.unit_price)}</td>
              <td>${String(line.monthly_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>{finding.cost_explanation}</p>
    </section>
  );
}
