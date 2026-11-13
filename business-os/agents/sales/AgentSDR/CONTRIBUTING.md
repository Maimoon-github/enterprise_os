# Contributing to AgentSDR

Thanks for taking the time to improve AgentSDR. This guide covers how to
propose a change, set up a development environment, and get a pull request
merged. By taking part you agree to follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — open an issue with the bug form. Include steps to
  reproduce and what you expected.
- **Suggest a feature** — open an issue with the feature form, describing
  the problem before the solution. Larger ideas start in
  [Discussions](https://github.com/Kandid-ai/AgentSDR/discussions).
- **Improve the docs** — typos, unclear steps and missing explanations are
  welcome as pull requests without an issue.
- **Fix an issue** — look for [`good first issue`](https://github.com/Kandid-ai/AgentSDR/labels/good%20first%20issue)
  and [`help wanted`](https://github.com/Kandid-ai/AgentSDR/labels/help%20wanted).

Security problems are **not** reported in issues — see [SECURITY.md](SECURITY.md).

## Before you start

- Search existing issues and pull requests first.
- For anything beyond a small fix, comment on the issue (or open one) and
  wait for a maintainer to confirm the approach. It saves you from building
  something that can't be merged.
- One issue per pull request; keep pull requests small and focused.

## Development setup

Full details are in [docs/development.md](docs/development.md). In short:

```sh
# Prerequisites: Bun ≥ 1.2, Node ≥ 20.9, PostgreSQL ≥ 16
git clone https://github.com/Kandid-ai/AgentSDR.git agentsdr
cd agentsdr
bun install
cp .env.example .env.local        # set DATABASE_URL, BETTER_AUTH_SECRET, …
bun run db:setup                  # creates the schema in an empty database
bun run db:seed:demo              # optional: demo user + fictional data
bun run dev                       # http://localhost:3000
```

The demo seed signs you in as `demo@example.com` / `demo-password-123`
in the "Northwind Demo" organization.

## Making a change

1. Fork the repository and create a branch from `main`
   (`fix/short-description`, `feat/short-description`, `docs/…`).
2. Make the change. Follow the conventions below and in [CLAUDE.md](CLAUDE.md),
   which is the project's rulebook for both humans and coding agents.
3. Run the checks — the same ones CI runs:

   ```sh
   bun run typecheck
   bun run lint
   bun run test
   bun run build        # for changes that touch pages, routes or config
   ```
4. Open a pull request against `main` and fill in the template.

### Conventions that matter here

- **TypeScript only.** No new `.js` / `.mjs` files.
- **Every piece of data belongs to an organization.** Any code that reads
  or writes the database follows
  [docs/multi-tenancy/conventions.md](docs/multi-tenancy/conventions.md):
  open the organization scope at the entry point, filter every query with
  `inOrg(...)`. A change to data access should leave
  `scripts/e2e/tenancy-isolation.ts` passing.
- **Database changes** come as a re-runnable migration in `scripts/` *plus*
  the matching Drizzle schema change *plus* a regenerated
  `db/schema.sql` (`bun run db:schema:dump`) — see
  [docs/database.md](docs/database.md). New tables are classified in
  `src/lib/tenancy/registry.ts`.
- **No secrets in code.** Third-party credentials are connected per
  organization in the app; platform settings come from the environment and
  are documented in [docs/configuration.md](docs/configuration.md) and
  `.env.example`.
- **Commit messages:** an area prefix and a plain summary — `Outreach:
  pause sends when the mailbox loses delegation` — with a body explaining
  *why* when it isn't obvious.

## Pull request review

- CI must be green (`CI / required`).
- A maintainer reviews within a few working days. Expect questions; they
  are about the code, not about you.
- UI changes include a screenshot or short recording.
- Maintainers squash-merge or rebase-merge; the PR title becomes the commit
  subject, so make it read well.

## License of contributions

AgentSDR is licensed under the [MIT License](LICENSE). By submitting a pull
request you agree that your contribution is licensed under the same license
(GitHub's inbound = outbound terms) and that you have the right to submit it.

## Getting help

See [SUPPORT.md](SUPPORT.md).
