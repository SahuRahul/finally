import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth } from "../helpers/api";

const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
  "NVDA", "META", "JPM", "V", "NFLX",
];

test.describe("Fresh start", () => {
  test.beforeEach(async ({ request }) => {
    await waitForHealth(request);
  });

  test("default watchlist, $10k cash, and streaming prices appear", async ({ page }) => {
    await page.goto("/");

    // Default 10-ticker watchlist renders
    for (const t of DEFAULT_TICKERS) {
      await expect(page.locator(sel.watchlistRow(t))).toBeVisible();
    }

    // $10,000 starting cash shown
    await expect(page.locator(sel.cashBalance)).toContainText("10,000");

    // Total portfolio value shown
    await expect(page.locator(sel.totalValue)).toBeVisible();

    // Connection indicator becomes connected (green)
    await expect(page.locator(sel.connectionStatus)).toHaveAttribute(
      "data-status",
      "connected",
    );

    // Prices stream: the AAPL price text changes within a few SSE ticks
    const priceCell = page.locator(`${sel.watchlistRow("AAPL")} [data-testid="price"]`);
    const first = await priceCell.textContent();
    await expect
      .poll(async () => priceCell.textContent(), { timeout: 8_000 })
      .not.toBe(first);
  });

  test("no uncaught console/page errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.goto("/");
    await expect(page.locator(sel.watchlist)).toBeVisible();
    expect(errors, errors.join("\n")).toHaveLength(0);
  });
});
