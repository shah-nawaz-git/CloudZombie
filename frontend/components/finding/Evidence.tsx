import type { FindingDetail } from "@/lib/types";
import { KeyValueTable } from "../KeyValueTable";
export function Evidence({ finding }: { finding: FindingDetail }) {
  return (
    <section className="panel">
      <h2>Current evidence</h2>
      <KeyValueTable value={finding.evidence} />
    </section>
  );
}
