<!-- Thanks for contributing! Keep the PR focused on one change. -->

## What and why

<!-- What does this change, and why is it needed? -->

Fixes #

## How it was tested

<!-- Commands you ran, what you clicked through, test data used. -->

## Screenshots

<!-- For UI changes: before / after. Remove personal data. -->

## Checklist

- [ ] `bun run typecheck`, `bun run lint` and `bun run test` pass
- [ ] Database access follows the [tenancy conventions](../docs/multi-tenancy/conventions.md) (scoped entry point, `inOrg` on every query)
- [ ] Schema change: migration in `scripts/`, Drizzle schema updated, `db/schema.sql` regenerated, new tables classified in `src/lib/tenancy/registry.ts` — or N/A
- [ ] New environment variables are in `.env.example` and `docs/configuration.md` — or N/A
- [ ] Docs updated where behaviour changed — or N/A
- [ ] No secrets or personal data in code, tests, fixtures or screenshots
