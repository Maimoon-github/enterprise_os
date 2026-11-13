---
name: write-e2e-test
description: Write or change a ChatterMate Playwright end-to-end test (e2e/). Use when adding e2e coverage for a feature, fixing a failing e2e spec, or adding a page object, fixture or fake-LLM script.
---

# Writing a ChatterMate e2e test

The suite lives in `e2e/`. Read `e2e/AUTHORING.md` first — it is the source of truth for
layout and rules. The essentials:

1. **Specs speak product language.** `specs/<feature>/<name>.spec.ts`, imports only from
   `@e2e`, no selectors (`page.locator`) and no raw HTTP — lint fails otherwise. Title ends
   with tags: `@<feature>`, plus `@smoke` only for the few journeys that must run on every PR.
2. **Selectors go in `src/pages/` (a screen) or `src/components/` (shared UI).** Prefer
   `getByRole`/`getByLabel`; if the element has no accessible name, add an `aria-label` to
   the Vue component rather than reaching for CSS. CSS needs a one-line "why" comment.
3. **Seed through `src/api/`, assert through the UI.** Need a new endpoint? Add a function to
   the matching `src/api/*.ts` module.
4. **Script the AI with `llm.script(agent, s => …)`** — `reply`, `handOver`, `createTicket`,
   `callTool(...).thenReply(...)`. Replies are structured ChatResponse JSON; handover and
   tickets are boolean fields, not tool calls.
5. **Fixtures give each test its own `agent` + `widget`.** `test.use({ agentSettings: { transferToHuman: true } })`
   for handover. `inbox` is Sam Agent's dashboard in a second browser. Never change org-wide
   settings outside a `*.org.spec.ts`.
6. **Prove it is stable** before finishing:
   `cd e2e && npx playwright test specs/<feature> --repeat-each=10 && npm run lint && npm run typecheck`
   (start the stack once with `./scripts/stack.sh up`; in a Claude worktree pass
   `E2E_PYTHON` and `E2E_FRONTEND_NODE_MODULES` pointing at the main checkout, and run with
   the sandbox disabled — Postgres, ports and the node_modules symlink need it).
7. **Update `e2e/FEATURES.md`** — the row for the journey, with the spec path and ✅.

Enterprise specs live in the private `enterprise_frontend` repo under `e2e/`, import only
from `@e2e`, and must never be added to this public repo.
