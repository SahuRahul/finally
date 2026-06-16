import { APIRequestContext, expect } from "@playwright/test";

/**
 * Thin wrappers over the backend REST API. Used to assert backend state
 * independently of the UI and to wait for readiness. Shapes follow PLAN.md
 * Section 8 and may be tightened once backend-api-engineer confirms them.
 */

export async function waitForHealth(request: APIRequestContext, retries = 60) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await request.get("/api/health");
      if (res.ok()) return;
    } catch {
      // server not up yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("Backend /api/health never became ready");
}

export async function getPortfolio(request: APIRequestContext) {
  const res = await request.get("/api/portfolio");
  expect(res.ok()).toBeTruthy();
  return res.json();
}

export async function getWatchlist(request: APIRequestContext) {
  const res = await request.get("/api/watchlist");
  expect(res.ok()).toBeTruthy();
  return res.json();
}

export async function getHistory(request: APIRequestContext) {
  const res = await request.get("/api/portfolio/history");
  expect(res.ok()).toBeTruthy();
  return res.json();
}
