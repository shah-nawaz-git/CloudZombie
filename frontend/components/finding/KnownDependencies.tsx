import type { FindingDetail } from "@/lib/types";
const supported: Record<string, string[]> = {
  ebs_volume: ["ebs_attachment"],
  elastic_ip: ["eip_association"],
  ec2_instance: ["attached_ebs_volume", "associated_elastic_ip"],
  ebs_snapshot: [
    "registered_ami",
    "shared_snapshot",
    "public_snapshot",
    "snapshot_lock",
    "aws_backup_managed",
  ],
};
export function KnownDependencies({ finding }: { finding: FindingDetail }) {
  return (
    <section className="panel">
      <h2>Known dependencies</h2>
      {finding.known_dependencies.length ? (
        <ul>
          {finding.known_dependencies.map((dependency, index) => (
            <li key={index}>
              {dependency.description}{" "}
              {dependency.blocks_remediation && <strong>— blocks remediation</strong>}
            </li>
          ))}
        </ul>
      ) : (
        <p>
          No dependencies found among the supported checks:{" "}
          {(supported[finding.resource_type] || []).join(", ")}.
        </p>
      )}
    </section>
  );
}
