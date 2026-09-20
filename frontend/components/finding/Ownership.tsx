import type { FindingDetail } from "@/lib/types";
import { OwnershipChip } from "../chips";
import { Mono } from "../Mono";
export function Ownership({ finding }: { finding: FindingDetail }) {
  return (
    <section className="panel">
      <h2>Infrastructure ownership</h2>
      <OwnershipChip label="Ownership" value={finding.ownership.status} />
      {finding.ownership.stack_name && (
        <p>
          Stack: <Mono>{finding.ownership.stack_name}</Mono> · logical ID{" "}
          <Mono>{finding.ownership.logical_id}</Mono>
        </p>
      )}
      {finding.ownership.notes.map((note) => (
        <p key={note}>{note}</p>
      ))}
      <p>Terraform: UNKNOWN (no reliable detection)</p>
    </section>
  );
}
