import Link from "next/link";
import type { Finding } from "@/lib/types";
export function FindingTitle({ finding }: { finding: Finding }) {
  return (
    <Link href={`/findings/${finding.id}`} className="mono">
      {finding.resource_id}
    </Link>
  );
}
