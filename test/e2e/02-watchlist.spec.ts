import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth } from "../helpers/api";

const NEW_TICKER = "PYPL";

test.describe("Watchlist add/remove", () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForHealth(request);
    await page.goto("/");
  });

  test("add a ticker then remove it", async ({ page }) => {
    // Add
    await page.locator(sel.watchlistAddInput).fill(NEW_TICKER);
    await page.locator(sel.watchlistAddBtn).click();

    const row = page.locator(sel.watchlistRow(NEW_TICKER));
    await expect(row).toBeVisible();

    // The new ticker streams a price (simulator picks it up)
    const priceCell = row.locator('[data-testid="price"]');
    await expect.poll(async () => (await priceCell.textContent())?.trim() || "", {
      timeout: 8_000,
    }).not.toBe("");

    // Remove
    await page.locator(sel.watchlistRemove(NEW_TICKER)).click();
    await expect(row).toBeHidden();
  });
});
