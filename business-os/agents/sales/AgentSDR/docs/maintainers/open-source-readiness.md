# Open-source readiness — plan and record

Status: done in the repository (1 Oct 2026); the owner actions under
"Before publishing" remain. This is the plan the release preparation followed
and the record of what was done and how it was verified. Nothing has been
pushed.

## How the plan was made

1. **Studied four comparable open-source products** through their GitHub
   repositories — Twenty (CRM, AGPL), Cal.com / Cal.diy (Next.js, MIT),
   Documenso (Next.js, AGPL), Formbricks (Next.js, AGPL open-core). Every
   one ships a LICENSE, a product README, CONTRIBUTING, a Contributor
   Covenant code of conduct, a SECURITY policy with a private channel and
   issue templates; most add a PR template, CI with a single required check,
   Dependabot, CodeQL, a Docker Compose self-host path, a one-command local
   setup and docs organised around self-hosting, configuration and
   architecture. None keeps code it is not prepared to publish.
2. **Audited this repository and its full git history** for secrets,
   personal data and internal infrastructure (read-only).
3. **Audited what a stranger needs** to go from `git clone` to a running,
   signed-in instance — and found the database could not be created from
   scratch.

## Findings that shaped the plan

| Finding | Severity | Resolution |
|---|---|---|
| The private development history contains an old credential | **Critical — needs the owner** | Rotate it; the public repository starts from a fresh history (see "Before publishing") |
| ~90 `refs/conductor-checkpoints/*` refs hold old snapshots | High | Never `--mirror`/`--all` push; delete before publishing |
| Real prospects' emails, a real phone number, a real LinkedIn handle and team mailboxes in test fixtures | High | Replaced with fictional data — done |
| Company sending domains, a sales contact sheet and a founder's profile hard-coded in three scripts | High | Scripts read local files; placeholder templates in `scripts/examples/` — done |
| No LICENSE (the chosen license, AGPL-3.0, was recorded only in `docs/design/enrichment-plan.md`) | P0 | Added — done |
| README is the create-next-app boilerplate | P0 | Product README with demo-data screenshots — done |
| No way to create a database from scratch (schema history is one-shot migrations against an existing database) | P0 | `db/schema.sql` + `db/seed.sql` + `db:setup` — done |
| No CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates, CI | P0 | Added — done |
| Self-host path undocumented; Docker image exists, no compose, no setup step in the image | P0 | Compose + docs — done (originally with a setup service and a cron sidecar; both are now in the app, Compose is `db` + `app`) |
| Lint has 38 pre-existing errors, so CI could not be green | P1 | Fixed or justified with scoped disables; legacy CommonJS migrations and the separate `video/` project scoped out — done |
| Product docs mixed with internal migration plans in `docs/` | P1 | User/maintainer docs; historical design notes moved to `docs/design/` — done |
| No demo data: contributors face an empty app, screenshots would show real data | P1 | `bun run db:seed:demo` — done |

## Decisions (made without blocking on the owner; each is easy to revisit)

- **License: AGPL-3.0-only**, as the project had already decided. (Changed to
  **MIT** on 8 October 2026, while all code was still Kandid's own, so no
  contributor consent was needed.) No
  enterprise carve-out: nothing in the tree is held back.
- **No CLA or DCO for now.** Contributions come in under the same license
  (GitHub's inbound = outbound terms); CONTRIBUTING says so. A CLA is a legal
  instrument the company must decide on — noted under "Before publishing".
- **Commit convention:** keep the existing "Area: summary" style and
  document it; no Conventional-Commits bot that the history would fail.
- **Docs stay Markdown in `docs/`** (rendered by GitHub). A docs site
  (Mintlify, Fumadocs) can be layered on later without moving files.
- **No large code restructuring.** The layout (`src/app`, `src/lib/<domain>`,
  `src/components`, `scripts/`, `extensions/`) is conventional for a single
  Next.js app; it is documented in `docs/architecture.md` instead of being
  moved, which would break every open branch for no user benefit.
- **`CLAUDE.md` / `AGENTS.md` stay**, as in all four reference repos; they
  are reviewed for internal-only content.

## Phases

Each phase ends with the checks listed under it; nothing is pushed.

### 1. Safety — done
- Secret / PII audit of HEAD and history (report above).
- Fixtures and scripts scrubbed; `.gitignore` hardened.
- Check: `git grep` for the removed identifiers returns only the GitHub org
  name; tests pass.

### 2. Legal and metadata — done
- `LICENSE` (AGPL-3.0), `package.json` license / repository / bugs /
  homepage / engines.

### 3. Reproducible install — done
- `db/schema.sql` (generated, 84 tables), `db/seed.sql`, `bun run db:setup`,
  `bun run db:schema:dump`, `bun run db:check`.
- Check: empty database → `db:setup` → `db:check` passes, on PostgreSQL 18
  and 17; second run refuses; the live-data rehearsal copy also passes
  `db:check`.

### 4. Community health files — done
- `README.md` (product README: what, features, screenshots, quick start,
  self-host, stack, docs, contributing, security, license).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1),
  `SECURITY.md` (private advisories first, email fallback, scope,
  timelines), `SUPPORT.md`, `CHANGELOG.md`, `GOVERNANCE.md`.
- `.github/`: issue forms (bug, feature) + `config.yml`, PR template,
  `CODEOWNERS` (template until a maintainers team exists), Dependabot.
- Check: Markdown link checker over every doc; YAML parses; issue forms
  validated against GitHub's schema keys.

### 5. Developer experience — done
- `.nvmrc`, `.editorconfig`, `.gitattributes`.
- Lint clean (fix, or justify with a scoped disable).
- Demo data seed (`bun run db:seed:demo`) with a demo user and fictional
  organization.
- Check: `bun install` → `db:setup` → `db:seed:demo` → `dev` → sign in as the
  demo user in a browser; typecheck, lint, tests, production build.

### 6. Self-hosting — done
- `docker-compose.yml` (Postgres + app), the image carrying `db/` and the setup
  script (run on start against an empty database). Originally a one-shot setup
  service and a cron sidecar; both are now in the app.
- Check: run the image's exact entrypoint (standalone server) and the setup
  script outside Docker against a fresh database (Docker is not available on
  the build machine); validate compose syntax.

### 7. CI/CD — done
- `ci.yml`: typecheck, lint, unit tests, production build, recorder
  extension build, fresh-database setup + audit on PostgreSQL 16/17/18, and
  one `required` job to protect `main` with.
- `codeql.yml`, `dependency-review.yml`, `docker.yml` (build on PRs, publish
  to GHCR on version tags), `stale.yml`.
- Check: `actionlint` on every workflow; every command a job runs is run
  locally first.

### 8. Documentation — done
- `docs/README.md` index; `self-hosting.md`, `configuration.md` (every env
  var, checked against the code), `integrations.md`, `architecture.md`,
  `development.md`, `database.md`; maintainer docs (`releasing.md`,
  `triage.md`); historical plans moved to `docs/design/` with references
  updated.
- Check: link checker; an env-reference check that every
  `process.env.X` in the code is documented.

### 9. Final verification — done
- From a clean checkout of `main`, with only CI's environment: `bun install
  --frozen-lockfile`, typecheck, lint (0 errors), unit tests (562 pass, 0
  fail), production build and recorder-extension build all pass.
- CI's database job replayed on an empty PostgreSQL 18 database: `db:setup`
  (84 tables), a second run refuses, `db:check` passes, the auth-policy
  checks pass, `db:seed:demo` seeds and `db:check` still passes. The same
  sequence passed earlier on PostgreSQL 17.
- The standalone server (the image's entrypoint) served sign-up, sign-in,
  organization creation and scoped API calls against a fresh database; the
  README screenshots were taken from it, on the demo organization only.
- Every relative link in `README.md` and `docs/` resolves; every documented
  `bun run` command exists.

## Before publishing (owner actions)

1. **Rotate the old database password** that is in history, and restrict
   that server's network access.
2. **Publish a clean history** with `bun run release:prepare` (see
   [releasing.md](releasing.md#publishing-the-public-repository)): a fresh
   single-commit repository from the committed tree. Never `git push --mirror`
   the private repository, and never push its `refs/conductor-checkpoints/*`.
3. Decide on a CLA (see Decisions).
4. Create the GitHub team named in `.github/CODEOWNERS`, enable private
   vulnerability reporting, Discussions, and branch protection on `main`
   requiring the `CI / required` check.
5. Set up the `security@kandid.ai` and `opensource@kandid.ai` mail routes
   named in `SECURITY.md` and `CODE_OF_CONDUCT.md`.
6. Review the launch video assets in `video/` (since moved to the private
   website repository) for real customer data before they go public. (The README screenshots in `docs/assets/screenshots/` show
   only the fictional demo organization.)
