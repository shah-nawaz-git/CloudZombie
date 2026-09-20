"use client";
import Link from "next/link";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { Mono } from "@/components/Mono";
import { PageHeader } from "@/components/PageHeader";
import { StatusChip } from "@/components/chips";
import { duration, formatTimestamp, money } from "@/lib/format";
import { useScans } from "@/lib/queries";
export default function ScansPage() {
  const scans = useScans();
  if (scans.isLoading) return <LoadingState />;
  if (scans.error) return <ErrorState error={scans.error} />;
  return (
    <>
      <PageHeader title="Scans">
        <p className="muted">Coverage and observation history from each read-only analysis run.</p>
      </PageHeader>
      <div className="panel table-wrap">
        <table aria-label="Scans table">
          <caption>Scans</caption>
          <thead>
            <tr>
              <th>Started</th>
              <th>Status</th>
              <th>Mode</th>
              <th>Regions</th>
              <th>New</th>
              <th>Persistent</th>
              <th>Resolved</th>
              <th>Estimated exposure</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {scans.data!.items.map((scan) => (
              <tr key={scan.id}>
                <td>
                  <Link href={`/scans/${scan.id}`}>
                    <Mono>{formatTimestamp(scan.started_at)}</Mono>
                  </Link>
                </td>
                <td>
                  <StatusChip value={scan.status} />
                </td>
                <td>
                  {scan.mode.toUpperCase()}{" "}
                  {scan.seeded && <span className="chip">seeded demo history</span>}
                </td>
                <td>
                  {scan.completed_regions.length > 0 && (
                    <span className="chip complete">{scan.completed_regions.length} complete</span>
                  )}{" "}
                  {scan.partial_regions.length > 0 && (
                    <span className="chip partial">{scan.partial_regions.length} partial</span>
                  )}{" "}
                  {scan.failed_regions.length > 0 && (
                    <span className="chip failed">{scan.failed_regions.length} failed</span>
                  )}{" "}
                  {scan.skipped_regions.length > 0 && (
                    <span className="chip skipped">{scan.skipped_regions.length} skipped</span>
                  )}
                </td>
                <td>{scan.new_findings}</td>
                <td>{scan.persistent_findings}</td>
                <td>{scan.resolved_findings}</td>
                <td>{money(scan.estimated_exposure)}</td>
                <td>{duration(scan.started_at, scan.finished_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
