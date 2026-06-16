# FinAlly E2E Tests

Playwright end-to-end tests covering PLAN.md Section 12. See `E2E_PLAN.md` for
the full scenario list and data-contract assumptions.

The suite is designed to run once against a fresh, empty database (default
$10k, default watchlist). The compose run gets this automatically (tmpfs DB
per run); for a local run, start the backend with a fresh `FINALLY_DB_PATH`.
Tests are order-independent (they assert deltas, not absolute holdings) but
assume the fresh-start baseline for the `01-fresh-start` scenario.

## Run against a locally running app

Start the full stack on port 8000 (FastAPI serving the Next.js export) with
`LLM_MOCK=true`, no `MASSIVE_API_KEY`, and a fresh `FINALLY_DB_PATH`, then:

```bash
cd test
npm install
npx playwright install --with-deps chromium
BASE_URL=http://localhost:8000 npm test
```

## Run the containerized stack (app + Playwright runner)

```bash
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

The app runs with `LLM_MOCK=true`, the built-in simulator, and a fresh
ephemeral SQLite DB each run (tmpfs at `/data`, where the image points
`FINALLY_DB_PATH`). Reports land in `test/playwright-report/`.

## Layout

- `e2e/` — spec files, one per scenario group
- `helpers/` — shared API helpers and centralized `data-testid` selectors
- `playwright.config.ts` — config; `BASE_URL` selects the target
- `docker-compose.test.yml` / `Dockerfile.playwright` — containerized run
