"use client";

import { ExposurePerScanChart } from "@/components/charts/ExposurePerScanChart";
import { FindingsPerScanChart } from "@/components/charts/FindingsPerScanChart";
import { CoverageMatrix } from "@/components/CoverageMatrix";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { PageHeader } from "@/components/PageHeader";
import { ScanControls } from "@/components/ScanControls";
import { StatStrip, type StatItem } from "@/components/StatStrip";
import { StatusChip } from "@/components/chips";
import { money, relativeTime } from "@/lib/format";
import { useCoverage, useHistory, useOverview } from "@/lib/queries";

export default function OverviewPage() {
  const overview = useOverview();
  const history = useHistory();
  const coverage = useCoverage();
  if (overview.isLoading || history.isLoading || coverage.isLoading) return <LoadingState />;
  if (overview.error) return <ErrorState error={overview.error} />;
  const data = overview.data!;
  const coverageSummary = [
    `${data.coverage_summary.complete} complete`,
    `${data.coverage_summary.partial} partial`,
    `${data.coverage_summary.failed} failed`,
    `${data.coverage_summary.skipped} skipped`,
  ].join(" · ");
  const stats: StatItem[] = [
    {
      value: money(data.estimated_monthly_cleanup_opportunity),
      label: "Estimated monthly cleanup opportunity",
      subline:
        data.potential_low_confidence_exposure > 0
          ? `plus ≤ ${money(data.potential_low_confidence_exposure)} potential snapshot exposure (low confidence)`
          : undefined,
    },
    { value: data.open_findings, label: "Open findings" },
    { value: data.persistent_low_risk_candidates, label: "Persistent low-risk candidates" },
    { value: data.review_required, label: "Review-required findings" },
    { value: data.high_risk, label: "High-risk findings" },
    { value: data.newly_observed, label: "Newly observed findings" },
    {
      value: data.regions_scanned.length,
      label: "Regions scanned",
      subline: coverageSummary,
    },
    {
      value: data.latest_scan ? <StatusChip value={data.latest_scan.status} /> : "—",
      label: "Latest scan",
      subline: data.latest_scan ? (
        <>
          {relativeTime(data.latest_scan.started_at)}
          {data.latest_scan.seeded && (
            <>
              {" "}
              · <span className="chip">seeded demo history</span>
            </>
          )}
        </>
      ) : undefined,
    },
    { value: data.resolved_in_latest_scan, label: "Newly resolved in latest scan" },
  ];
  return (
    <>
      <PageHeader title="Overview">
        <p className="muted">AWS cleanup planning with read-only analysis.</p>
      </PageHeader>
      <StatStrip items={stats} />
      <section className="panel">
        <h2>Scan controls</h2>
        <ScanControls />
      </section>
      <div className="grid-2">
        <section className="panel">
          <h2>Findings observed per scan</h2>
          <FindingsPerScanChart points={history.data?.points || []} />
        </section>
        <section className="panel">
          <h2>Estimated exposure per scan</h2>
          <ExposurePerScanChart points={history.data?.points || []} />
        </section>
      </div>
      <section className="panel">
        <h2>Latest coverage</h2>
        {coverage.data && <CoverageMatrix coverage={coverage.data} />}
      </section>
    </>
  );
}
