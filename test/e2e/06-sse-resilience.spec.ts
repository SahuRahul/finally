import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth } from "../helpers/api";

test.describe("SSE resilience", () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForHealth(request);
    await page.goto("/");
    await expect(page.locator(sel.connectionStatus)).toHaveAttribute(
      "data-status",
      "connected",
    );
  });

  test("EventSource reconnects after a connection failure and prices resume", async ({
    page,
  }) => {
    const priceCell = page.locator(`${sel.watchlistRow("AAPL")} [data-testid="price"]`);

    // Force the SSE connection to fail by aborting requests to the stream
    // endpoint, then reload so a fresh EventSource is created under the route
    // and immediately errors (onerror -> not "connected"). Only the stream
    // endpoint is blocked; the page's own assets still load. Aborting after
    // the socket is already open would not affect the live connection.
    await page.route("**/api/stream/prices", (route) => route.abort());
    await page.reload();
    await expect
      .poll(async () => page.locator(sel.connectionStatus).getAttribute("data-status"), {
        timeout: 10_000,
      })
      .not.toBe("connected");

    // Stop aborting; the next EventSource auto-retry succeeds.
    await page.unroute("**/api/stream/prices");

    // Indicator recovers to connected.
    await expect(page.locator(sel.connectionStatus)).toHaveAttribute(
      "data-status",
      "connected",
      { timeout: 15_000 },
    );

    // Prices resume updating after reconnection.
    const resumed = await priceCell.textContent();
    await expect
      .poll(async () => priceCell.textContent(), { timeout: 12_000 })
      .not.toBe(resumed);
  });
});
