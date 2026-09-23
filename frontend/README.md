# CloudZombie frontend

Next.js App Router UI for CloudZombie. It renders the overview, findings table, finding detail (evidence, observation history, known dependencies, ownership, cost, cleanup plan, and guarded script preview), scan history, settings, and about pages.

All data comes from the FastAPI backend through same-origin `/api/*` requests. `proxy.ts` forwards them to `BACKEND_URL` when each request arrives, so the production image works with any backend address.

## Commands

```bash
npm ci
BACKEND_URL=http://localhost:8000 npm run dev      # http://localhost:3000
npm run lint
npm run format:check
npx tsc --noEmit
npm run test                                        # Vitest + Testing Library + MSW
npm run build                                       # standalone production build
E2E_BASE_URL=http://127.0.0.1:3000 npx playwright test
```

The Playwright flow expects a running backend and frontend; in CI it runs against the Docker Compose stack.

See the repository [README](../README.md) and [docs/](../docs) for the product, security model, and API contract.
