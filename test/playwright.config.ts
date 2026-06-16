import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for FinAlly E2E tests.
 *
 * BASE_URL points at the running full stack (FastAPI serving the Next.js
 * static export on port 8000). Defaults to localhost for local runs; the
 * docker-compose.test.yml sets it to the app service.
 */
const baseURL = process.env.BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
