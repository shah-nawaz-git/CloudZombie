import { test, expect } from "@playwright/test";
test("demo cleanup planning flow", async ({ page }) => {
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/");
  await expect(page.getByText("DEMO MODE")).toBeVisible();
  await page.getByRole("button", { name: "Run scan" }).click();
  await expect(page.getByText(/new \d+ · persistent \d+ · resolved \d+/)).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByText("Estimated monthly cleanup opportunity")).toBeVisible();
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("link", { name: "vol-0a1b2c3d4e5f60001" }).click();
  await expect(page.getByText("Resource age", { exact: true })).toBeVisible();
  await expect(page.getByText("First observed unattached", { exact: true })).toBeVisible();
  await expect(page.getByText("Observed unattached", { exact: true })).toBeVisible();
  await expect(page.getByText(/\d+ scans/)).toBeVisible();
  await expect(page.getByText("$47.60", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Known dependencies" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Infrastructure ownership" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cleanup plan" })).toBeVisible();
  const script = page.locator("pre.code");
  await expect(script).toContainText('EXPECTED_ACCOUNT_ID="123456789012"');
  await expect(script).toContainText('REGION="eu-central-1"');
  await expect(script).toContainText('VOLUME_ID="vol-0a1b2c3d4e5f60001"');
  await expect(script).toContainText("describe-volumes");
  await expect(script).toContainText("cloudzombie:ignore");
  await expect(script).toContainText("Type DELETE");
  await page.getByRole("link", { name: "Scans" }).click();
  await expect(page.getByText("PARTIAL").first()).toBeVisible();
  await page.locator("tbody tr").first().getByRole("link").click();
  await expect(page.getByText("ec2:DescribeSnapshots").first()).toBeVisible();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Runtime mode" })).toBeVisible();

  expect(pageErrors).toEqual([]);
  expect(serverErrors).toEqual([]);
});
