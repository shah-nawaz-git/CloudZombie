"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import type { Scan } from "@/lib/types";
import { CoverageMatrix } from "./CoverageMatrix";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { Mono } from "./Mono";
import { PageHeader } from "./PageHeader";
import { StatusChip } from "./chips";
export function ScanDetail({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["scan", id], queryFn: () => api<Scan>(`/api/scans/${id}`) });
  if (query.isLoading) return <LoadingState />;
  if (query.error) return <ErrorState error={query.error} />;
  const scan = query.data!;
  return (
    <>
      <PageHeader title="Scan detail">
        <Mono>{scan.id}</Mono>
      </PageHeader>
      {scan.status === "partial" && (
        <div className="banner">
          Partial coverage: analysis did not run everywhere — see the matrix
        </div>
      )}
      <section className="panel">
        <h2>Scan summary</h2>
        <StatusChip value={scan.status} />
        <p>
          Started <Mono>{formatTimestamp(scan.started_at)}</Mono> · Finished{" "}
          <Mono>{formatTimestamp(scan.finished_at)}</Mono>
        </p>
        <p>Complete: {scan.completed_regions.join(", ") || "none"}</p>
        <p>Partial: {scan.partial_regions.join(", ") || "none"}</p>
        <p>Failed: {scan.failed_regions.join(", ") || "none"}</p>
        <p>Skipped: {scan.skipped_regions.join(", ") || "none"}</p>
      </section>
      <section className="panel">
        <h2>Coverage</h2>
        <CoverageMatrix coverage={{ regions: scan.coverage }} />
      </section>
      <section className="panel">
        <h2>Errors and warnings</h2>
        {scan.errors.length ? (
          <pre className="code">{JSON.stringify(scan.errors, null, 2)}</pre>
        ) : (
          <p>No scan errors.</p>
        )}
      </section>
    </>
  );
}
