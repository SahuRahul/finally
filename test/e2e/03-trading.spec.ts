import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth, getPortfolio } from "../helpers/api";

const TICKER = "AAPL";

/** Parse a currency-ish string like "$9,810.50" -> 9810.5 */
function parseMoney(text: string | null): number {
  if (!text) return NaN;
  return parseFloat(text.replace(/[^0-9.-]/g, ""));
}

test.describe("Trading", () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForHealth(request);
    await page.goto("/");
  });

  async function qtyOf(request: import("@playwright/test").APIRequestContext, ticker: string) {
    const p = await getPortfolio(request);
    return p.positions.find((x: any) => x.ticker === ticker)?.quantity ?? 0;
  }

  test("buy shares: cash decreases, position appears", async ({ page, request }) => {
    const before = await getPortfolio(request);
    const beforeQty = await qtyOf(request, TICKER);

    await page.locator(sel.tradeTicker).fill(TICKER);
    await page.locator(sel.tradeQuantity).fill("5");
    await page.locator(sel.tradeBuyBtn).click();

    // Position row appears with the bought ticker
    await expect(page.locator(sel.positionRow(TICKER))).toBeVisible();

    // Cash decreased
    await expect
      .poll(async () => (await getPortfolio(request)).cash_balance, { timeout: 8_000 })
      .toBeLessThan(before.cash_balance);

    // Held quantity grew by ~5 (delta, so the test is order/repeat-independent)
    await expect
      .poll(async () => qtyOf(request, TICKER), { timeout: 8_000 })
      .toBeCloseTo(beforeQty + 5, 5);
  });

  test("sell shares: cash increases and position quantity drops", async ({
    page,
    request,
  }) => {
    // Buy a known quantity, then wait until the backend reflects it (settled).
    await page.locator(sel.tradeTicker).fill(TICKER);
    await page.locator(sel.tradeQuantity).fill("5");
    await page.locator(sel.tradeBuyBtn).click();
    await expect(page.locator(sel.positionRow(TICKER))).toBeVisible();
    await expect.poll(async () => qtyOf(request, TICKER)).toBeGreaterThanOrEqual(5);

    const beforeCash = (await getPortfolio(request)).cash_balance;
    const beforeQty = await qtyOf(request, TICKER);

    // The buy handler clears the quantity field (setQuantity("")) only after
    // its request settles. Wait for that to land before re-filling, otherwise
    // a late clear can wipe our sell quantity and the sell submits empty.
    await expect(page.locator(sel.tradeQuantity)).toHaveValue("");
    await page.locator(sel.tradeTicker).fill(TICKER);
    await page.locator(sel.tradeQuantity).fill("5");
    await expect(page.locator(sel.tradeSellBtn)).toBeEnabled();
    await page.locator(sel.tradeSellBtn).click();

    // Cash increases and the held quantity drops by ~5 (order-independent:
    // other tickers/shares may exist, so assert the delta, not liquidation).
    await expect
      .poll(async () => (await getPortfolio(request)).cash_balance, { timeout: 8_000 })
      .toBeGreaterThan(beforeCash);
    await expect
      .poll(async () => qtyOf(request, TICKER), { timeout: 8_000 })
      .toBeCloseTo(beforeQty - 5, 5);
  });
});
