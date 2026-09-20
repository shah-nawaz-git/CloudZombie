"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BulkScriptPanel, type BulkResult } from "@/components/findings/BulkScriptPanel";
import { FiltersBar } from "@/components/findings/FiltersBar";
import { FindingsTable } from "@/components/findings/FindingsTable";
import { Pagination } from "@/components/findings/Pagination";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { PageHeader } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { useCoverage, useFindings } from "@/lib/queries";
function FindingsContent() {
  const search = useSearchParams();
  const router = useRouter();
  const parameters = new URLSearchParams(search.toString());
  if (!parameters.has("status")) parameters.append("status", "open");
  if (!parameters.has("sort")) {
    parameters.set("sort", "estimated_monthly_cost");
    parameters.set("order", "desc");
  }
  const query = useFindings(parameters.toString());
  const coverage = useCoverage();
  const [selected, setSelected] = useState<string[]>([]);
  const [bulk, setBulk] = useState<BulkResult | null>(null);
  function navigate(next: URLSearchParams) {
    next.set("page", "1");
    router.replace(`/findings?${next}`);
  }
  function setParam(key: string, value: string) {
    const next = new URLSearchParams(search.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    navigate(next);
  }
  function goPage(page: number) {
    const next = new URLSearchParams(search.toString());
    next.set("page", String(page));
    router.replace(`/findings?${next}`);
  }
  function setStatuses(values: string[]) {
    const next = new URLSearchParams(search.toString());
    next.delete("status");
    values.forEach((value) => next.append("status", value));
    navigate(next);
  }
  function sortBy(field: string) {
    const next = new URLSearchParams(search.toString());
    const current = next.get("sort") || "estimated_monthly_cost";
    const order = current === field && (next.get("order") || "desc") === "desc" ? "asc" : "desc";
    next.set("sort", field);
    next.set("order", order);
    navigate(next);
  }
  async function generate() {
    setBulk(
      await api<BulkResult>("/api/scripts/bulk", {
        method: "POST",
        body: JSON.stringify({ finding_ids: selected }),
      }),
    );
  }
  if (query.isLoading) return <LoadingState />;
  if (query.error) return <ErrorState error={query.error} />;
  const data = query.data!;
  return (
    <>
      <PageHeader title="Findings">
        <p className="muted">
          Review observed conditions, known dependencies, ownership, and list-price exposure.
        </p>
      </PageHeader>
      <FiltersBar
        search={search}
        regions={Object.keys(coverage.data?.regions || {})}
        setParam={setParam}
        setStatuses={setStatuses}
      />
      <BulkScriptPanel selectedCount={selected.length} result={bulk} generate={generate} />
      {data.items.length === 0 ? (
        <EmptyState>
          No findings match these filters. Adjust the filters or run another scan.
        </EmptyState>
      ) : (
        <FindingsTable
          findings={data.items}
          selected={selected}
          setSelected={setSelected}
          sort={parameters.get("sort") || "estimated_monthly_cost"}
          order={parameters.get("order") || "desc"}
          onSort={sortBy}
        />
      )}
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} go={goPage} />
    </>
  );
}
export default function FindingsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <FindingsContent />
    </Suspense>
  );
}
