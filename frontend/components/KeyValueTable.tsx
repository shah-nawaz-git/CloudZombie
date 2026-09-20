import { formatTimestamp } from "@/lib/format";

const LABELS: Record<string, string> = {
  state: "State",
  volume_type: "Volume type",
  device_name: "Device name",
  volume_id: "Volume ID",
  availability_zone: "Availability zone",
  size_gib: "Size (GiB)",
  iops: "IOPS",
  throughput_mibps: "Throughput (MiB/s)",
  encrypted: "Encrypted",
  created_at: "Created at",
  origin_snapshot_id: "Origin snapshot",
  attachment_count: "Attachments",
  name_tag: "Name tag",
  tags: "Tags",
  snapshot_id: "Snapshot ID",
  source_volume_id: "Source volume",
  started_at: "Snapshot started",
  volume_size_gib: "Snapshot size (GiB)",
  storage_tier: "Storage tier",
  description: "Description",
  ami_references: "AMI references",
  shared_with_account_ids: "Shared with accounts",
  shared_publicly: "Shared publicly",
  lock_state: "Lock state",
  aws_backup_managed: "AWS Backup managed",
  source_volume_exists: "Source volume exists",
  instance_id: "Instance ID",
  instance_type: "Instance type",
  launched_at: "Launch time (last start)",
  launch_time_note: "Note",
  platform: "Platform",
  attached_volumes: "Attached volumes",
  attached_storage_gib: "Attached storage (GiB)",
  associated_public_ipv4: "Associated public IPv4",
  allocation_id: "Allocation ID",
  public_ip: "Public IP",
  domain: "Domain",
  association_id: "Association ID",
  network_interface_id: "Network interface",
};
const TIMESTAMPS = new Set(["created_at", "started_at", "launched_at"]);
function displayValue(key: string, value: unknown) {
  if (value == null) return "—";
  if (TIMESTAMPS.has(key) && typeof value === "string") return formatTimestamp(value);
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
function ObjectArray({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  return (
    <table className="nested-table">
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column}>{LABELS[column] || column}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index}>
            {columns.map((column) => (
              <td key={column} className="mono">
                {displayValue(column, row[column])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
export function KeyValueTable({ value }: { value: Record<string, unknown> }) {
  return (
    <table className="kv" aria-label="Current evidence">
      <tbody>
        {Object.entries(value).map(([key, item]) => (
          <tr key={key}>
            <td>{LABELS[key] ? LABELS[key] : <code>{key}</code>}</td>
            <td>
              {key === "tags" && item && typeof item === "object" ? (
                <table className="tag-table">
                  <thead>
                    <tr>
                      <th>Tag key</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(item as Record<string, string>).map(([tag, tagValue]) => (
                      <tr key={tag}>
                        <td className="mono">{tag}</td>
                        <td>{tagValue}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : Array.isArray(item) && item.length > 0 && typeof item[0] === "object" ? (
                <ObjectArray rows={item as Record<string, unknown>[]} />
              ) : (
                <span className={Array.isArray(item) ? "mono" : ""}>{displayValue(key, item)}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
