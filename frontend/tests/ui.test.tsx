import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, it, vi } from "vitest";
import { server } from "./setup";
import identity from "./fixtures/identity.json";
import overview from "./fixtures/overview.json";
import history from "./fixtures/history.json";
import coverage from "./fixtures/coverage.json";
import findings from "./fixtures/findings.json";
import hero from "./fixtures/hero-finding.json";
import plan from "./fixtures/hero-plan.json";
import script from "./fixtures/hero-script.json";
import snapshot from "./fixtures/snapshot-finding.json";
import settings from "./fixtures/settings.json";
import completed from "./fixtures/scan-completed.json";
import { ModeBadge, ErrorState } from "@/components/ui";
import OverviewPage from "@/app/page";
import FindingsPage from "@/app/findings/page";
import { FindingDetail } from "@/components/FindingDetail";
import { ScanDetail } from "@/components/ScanDetail";
import type { Identity } from "@/lib/types";
import SettingsPage from "@/app/settings/page";
import AboutPage, { IAM_ACTIONS } from "@/app/about/page";
import { historyChartData } from "@/lib/chart-data";
import { FindingsPerScanChart } from "@/components/charts/FindingsPerScanChart";
import { ExposurePerScanChart } from "@/components/charts/ExposurePerScanChart";
import policy from "../../docs/iam-policy.json";
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/findings",
  useRouter: () => ({ replace, push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("recharts", () => {
  const Box = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  const Bar = ({
    isAnimationActive,
    dataKey,
  }: {
    isAnimationActive?: boolean;
    dataKey?: string;
  }) => (
    <div data-testid="chart-bar" data-series={dataKey} data-animation={String(isAnimationActive)} />
  );
  const Line = ({
    isAnimationActive,
    dataKey,
  }: {
    isAnimationActive?: boolean;
    dataKey?: string;
  }) => (
    <div
      data-testid="chart-line"
      data-series={dataKey}
      data-animation={String(isAnimationActive)}
    />
  );
  return {
    ResponsiveContainer: Box,
    BarChart: Box,
    LineChart: Box,
    CartesianGrid: Box,
    XAxis: Box,
    YAxis: Box,
    Tooltip: Box,
    Legend: Box,
    Bar,
    Line,
  };
});
function wrapper(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
const json = (path: string, value: unknown) =>
  http.get(`*${path}`, () => HttpResponse.json(value as Record<string, unknown>));
beforeEach(() => {
  replace.mockReset();
});
it("renders DEMO and LIVE mode badges", () => {
  const { rerender } = render(<ModeBadge identity={identity as Identity} />);
  expect(screen.getByText("DEMO MODE")).toBeInTheDocument();
  rerender(
    <ModeBadge identity={{ ...identity, mode: "live", account_id: "123456789012" } as Identity} />,
  );
  expect(screen.getByText(/LIVE AWS/)).toBeInTheDocument();
});
it("overview renders opportunity stats and coverage", async () => {
  server.use(
    json("/api/overview", overview),
    json("/api/history", history),
    json("/api/coverage", coverage),
  );
  wrapper(<OverviewPage />);
  expect(await screen.findByText("$150.27")).toBeInTheDocument();
  expect(screen.getByText("Open findings")).toBeInTheDocument();
  expect(screen.getByText("Findings observed per scan")).toBeInTheDocument();
});
it("scan control polls running to completion", async () => {
  let count = 0;
  server.use(
    json("/api/overview", overview),
    json("/api/history", history),
    json("/api/coverage", coverage),
    http.post("*/api/scans", () => HttpResponse.json({ ...completed, status: "running" })),
    http.get(`*/api/scans/${completed.id}`, () =>
      HttpResponse.json(++count > 0 ? completed : { ...completed, status: "running" }),
    ),
  );
  wrapper(<OverviewPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Run scan" }));
  expect(await screen.findByText(/new 0 · persistent/, {}, { timeout: 2500 })).toBeInTheDocument();
});
it("findings table separates resource age and first observed and avoids forbidden wording", async () => {
  server.use(
    http.get("*/api/findings", () => HttpResponse.json(findings)),
    json("/api/coverage", coverage),
  );
  wrapper(<FindingsPage />);
  const table = await screen.findByRole("table", { name: "Findings table" });
  expect(screen.getByText("Resource Age")).toBeInTheDocument();
  expect(screen.getByText("First Observed")).toBeInTheDocument();
  expect(table.textContent).toContain("180 days");
  expect(table.textContent).toContain(`${hero.first_observed_days_ago} days ago`);
  expect(table.textContent).not.toMatch(
    /(unattached|unassociated|stopped|idle|unused|orphan)\w* for \d+ (days|scans)/i,
  );
});
it("filters update URL", async () => {
  server.use(
    http.get("*/api/findings", () => HttpResponse.json(findings)),
    json("/api/coverage", coverage),
  );
  wrapper(<FindingsPage />);
  await userEvent.selectOptions(await screen.findByLabelText("Resource type"), "ebs_volume");
  expect(replace).toHaveBeenCalledWith(expect.stringContaining("resource_type=ebs_volume"));
});
it("estimated cost sort toggles ascending in the URL", async () => {
  server.use(
    http.get("*/api/findings", () => HttpResponse.json(findings)),
    json("/api/coverage", coverage),
  );
  wrapper(<FindingsPage />);
  await userEvent.click(await screen.findByRole("button", { name: /Estimated Cost/ }));
  expect(replace).toHaveBeenCalledWith(
    expect.stringContaining("sort=estimated_monthly_cost&order=asc"),
  );
});
it("chart data flattens resource counts", () => {
  const transformed = historyChartData(history.points as never);
  expect(transformed[0].ebs_volume).toBeGreaterThan(0);
  expect(transformed[0].ebs_snapshot).toBeGreaterThan(0);
});
it("charts disable series animations", () => {
  const points = history.points as never;
  const { unmount } = render(<FindingsPerScanChart points={points} />);
  expect(screen.getAllByTestId("chart-bar")).toHaveLength(4);
  expect(
    screen.getAllByTestId("chart-bar").every((item) => item.dataset.animation === "false"),
  ).toBe(true);
  unmount();
  render(<ExposurePerScanChart points={points} />);
  expect(screen.getAllByTestId("chart-line")).toHaveLength(2);
  expect(
    screen.getAllByTestId("chart-line").every((item) => item.dataset.animation === "false"),
  ).toBe(true);
});
it("detail renders every critical section and safe generated script", async () => {
  server.use(
    json(`/api/findings/${hero.id}`, hero),
    json(`/api/findings/${hero.id}/plan`, plan),
    json(`/api/findings/${hero.id}/script`, script),
  );
  wrapper(<FindingDetail id={hero.id} />);
  for (const heading of [
    "Why it was flagged",
    "Observation history",
    "Current evidence",
    "Known dependencies",
    "Infrastructure ownership",
    "Cost calculation",
    "Uncertainty and limitations",
    "Cleanup plan",
    "Generated script",
    "Observation timeline",
  ])
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  expect(screen.getByText("Resource age")).toBeInTheDocument();
  expect(screen.getByText("First observed unattached")).toBeInTheDocument();
  expect(screen.getByText(`${hero.first_observed_days_ago} days ago`)).toBeInTheDocument();
  expect(screen.getByText("Observed unattached")).toBeInTheDocument();
  expect(screen.getByText(/readonly VOLUME_ID="vol-0a1b2c3d4e5f60001"/)).toBeInTheDocument();
  expect(document.body.textContent).toContain("cloudzombie:ignore");
  expect(document.body.textContent).not.toMatch(/orphan/i);
});
it("snapshot detail shows upper bound and never forbidden snapshot term", async () => {
  const snapshotPlan = {
    ...plan,
    finding_id: snapshot.id,
    resource_id: snapshot.resource_id,
    estimated_cost: { ...plan.estimated_cost, upper_bound: true },
  };
  server.use(
    json(`/api/findings/${snapshot.id}`, snapshot),
    json(`/api/findings/${snapshot.id}/plan`, snapshotPlan),
    json(`/api/findings/${snapshot.id}/script`, { ...script, kind: "investigation" }),
  );
  wrapper(<FindingDetail id={snapshot.id} />);
  expect((await screen.findAllByText(/≤ \$/)).length).toBeGreaterThan(0);
  expect(screen.getByText(/Upper bound/)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/orphan/i);
});
it("scan detail shows partial coverage operation", async () => {
  server.use(json(`/api/scans/${completed.id}`, completed));
  wrapper(<ScanDetail id={completed.id} />);
  expect(await screen.findByText(/Partial coverage/)).toBeInTheDocument();
  expect(screen.getAllByText("ec2:DescribeSnapshots").length).toBeGreaterThan(0);
});
it("settings PATCH round trip", async () => {
  server.use(
    json("/api/settings", settings),
    http.patch("*/api/settings", async ({ request }) =>
      HttpResponse.json({ ...settings, ...((await request.json()) as object) }),
    ),
  );
  wrapper(<SettingsPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Save settings" }));
  expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
});
it("ErrorState displays credentials hint", () => {
  render(
    <ErrorState
      error={{ code: "aws_credentials", message: "Missing credentials", hint: "Use demo mode" }}
    />,
  );
  expect(screen.getByText("Use demo mode")).toBeInTheDocument();
});
it("about IAM actions equal policy", () => {
  render(<AboutPage />);
  expect(IAM_ACTIONS).toEqual(policy.Statement[0].Action);
  expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(12);
});
