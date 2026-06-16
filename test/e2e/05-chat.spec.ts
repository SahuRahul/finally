import { test, expect } from "@playwright/test";
import { sel } from "../helpers/selectors";
import { waitForHealth, getPortfolio, getWatchlist } from "../helpers/api";

/**
 * AI chat with LLM_MOCK=true. The mock branches on message content
 * (confirmed by llm-engineer). Triggers and exact response strings below match
 * the deterministic mock contract.
 *
 * Response shape: {message: string, actions: Array}.
 *   trade action:     {type:"trade", status:"executed"|"error", ticker, side, quantity, price?, error?}
 *   watchlist action: {type:"watchlist", status:"executed", ticker, action:"add"|"remove"}
 * Validation failures return status:"error" with HTTP 200 (check action.status).
 */
const MOCK = {
  analysisPrompt: "How is my portfolio doing?",
  analysisReply:
    "Here is a summary of your portfolio. Ask me to buy or sell shares, or to add or remove tickers from your watchlist.",
  tradePrompt: "buy 2 AAPL",
  tradeReply: "Buying 2 shares of AAPL.",
  tradeTicker: "AAPL",
  watchlistPrompt: "add PYPL to watchlist",
  watchlistReply: "Added PYPL to your watchlist.",
  watchlistTicker: "PYPL",
};

async function send(page: import("@playwright/test").Page, text: string) {
  await page.locator(sel.chatInput).fill(text);
  await page.locator(sel.chatSendBtn).click();
}

test.describe("AI chat (mocked)", () => {
  test.beforeEach(async ({ request, page }) => {
    await waitForHealth(request);
    await page.goto("/");
  });

  test("send a plain message and receive the deterministic summary reply", async ({
    page,
  }) => {
    await send(page, MOCK.analysisPrompt);
    await expect(page.locator(sel.chatMessage).last()).toContainText(
      MOCK.analysisReply,
    );
    // Plain analysis carries no actions
    await expect(page.locator(sel.chatAction)).toHaveCount(0);
  });

  test("chat-executed trade shows inline confirmation and updates portfolio", async ({
    page,
    request,
  }) => {
    const before = await getPortfolio(request);
    await send(page, MOCK.tradePrompt);

    // Assistant confirms with the deterministic reply
    await expect(page.locator(sel.chatMessage).last()).toContainText(
      MOCK.tradeReply,
    );
    // Inline action confirmation rendered in the chat
    await expect(page.locator(sel.chatAction).last()).toBeVisible();

    // Backend reflects the executed trade
    await expect
      .poll(async () => {
        const p = await getPortfolio(request);
        return p.positions.some((x: any) => x.ticker === MOCK.tradeTicker);
      }, { timeout: 8_000 })
      .toBeTruthy();
    const after = await getPortfolio(request);
    expect(after.cash_balance).toBeLessThan(before.cash_balance);
  });

  test("chat watchlist change reflects in watchlist", async ({ page, request }) => {
    await send(page, MOCK.watchlistPrompt);
    await expect(page.locator(sel.chatAction).last()).toBeVisible();
    await expect
      .poll(async () => {
        const w = await getWatchlist(request);
        return JSON.stringify(w).includes(MOCK.watchlistTicker);
      }, { timeout: 8_000 })
      .toBeTruthy();
  });
});
