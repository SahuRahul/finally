import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth } from "../helpers/api";

test.describe("Portfolio visualization", () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForHealth(request);
    await page.goto("/");
  });

  test("heatmap renders and P&L chart has data after a trade", async ({ page }) => {
    // Create a position so the heatmap has something to draw
    await page.locator(sel.tradeTicker).fill("MSFT");
    await page.locator(sel.tradeQuantity).fill("3");
    await page.locator(sel.tradeBuyBtn).click();
    await expect(page.locator(sel.positionRow("MSFT")).first()).toBeVisible();

    // Heatmap shows at least one rectangle (a position tile)
    const heatmap = page.locator(sel.portfolioHeatmap);
    await expect(heatmap).toBeVisible();
    await expect(heatmap.locator("rect, [data-testid='heatmap-tile']").first()).toBeVisible();

    // P&L chart has at least one plotted point/path after a snapshot
    const chart = page.locator(sel.pnlChart);
    await expect(chart).toBeVisible();
    await expect
      .poll(async () => chart.locator("path, circle, rect").count(), { timeout: 12_000 })
      .toBeGreaterThan(0);
  });
});
