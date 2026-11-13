# Releasing

## Versioning

AgentSDR follows [Semantic Versioning](https://semver.org). Releases are Git
tags of the form `vX.Y.Z` on `main`. While the major version is 0, minor
releases may include breaking changes; say so in the notes.

What counts as a breaking change for a self-hoster: a removed or renamed
environment variable, a required manual migration, a changed webhook URL, or a
change that requires reconnecting integrations.

## Changelog

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com). Add
entries under `Unreleased` as changes merge (Added, Changed, Deprecated,
Removed, Fixed, Security). At release time, rename `Unreleased` to the version
and date and start a fresh `Unreleased` section.

## Container image

The `docker.yml` workflow builds the image from the `Dockerfile` on pull
requests (to prove it builds) and publishes it to
`ghcr.io/kandid-ai/agentsdr` when a `v*` tag is pushed. The tag `vX.Y.Z`
produces the matching image tag.

## Release checklist

1. **CI is green on `main`** (the `CI / required` check: typecheck, lint, tests,
   production build, recorder build, fresh-database setup and audit on
   PostgreSQL 16, 17 and 18).
2. **Migrations.** List every script added to `scripts/` since the last tag:
   `git log --diff-filter=A --name-only --format= vPREVIOUS..HEAD -- scripts/`.
   Each one that an existing install must run goes in the release notes, in
   order, with the command (`bun scripts/<name>.ts`).
3. **Schema snapshot.** `db/schema.sql` matches the migrated schema: apply the
   migrations to a scratch database, run `bun run db:schema:dump`, and confirm
   there is no diff. `bun run db:check` passes.
4. **Fresh install works.** On an empty database: `bun run db:setup`, then
   `bun run db:check`.
5. **Configuration changes.** Any new, renamed or removed environment variable
   is in `.env.example` and [../configuration.md](../configuration.md), and
   called out in the notes.
6. **Upgrade notes.** Anything an operator must do besides pulling and
   rebuilding (new scheduled job or endpoint, new webhook, key rotation) is written down
   in the release notes and in [../self-hosting.md](../self-hosting.md) if it is
   permanent.
7. **Changelog and version.** Update `CHANGELOG.md`; set `version` in
   `package.json`, and the same version as the image tag default in
   `docker-compose.yml` (`${AGENTSDR_VERSION:-X.Y.Z}`, also inlined in
   `docs/self-hosting/docker-compose.mdx`). CI fails if they differ.
8. **Tag.** `git tag vX.Y.Z && git push origin vX.Y.Z`. Confirm the Docker
   workflow publishes the image.
9. **GitHub release.** Create a release from the tag, paste the changelog
   section, and add the migration list and upgrade notes at the top.

## Publishing the public repository

The public repository starts from a fresh history: the private one holds
material that is never published. `release:prepare` builds it from the
committed tree at `HEAD`:

```sh
bun run release:prepare -- --out ../agentsdr-public --repo <owner>/<name> --message "AgentSDR 0.1.0"
```

It refuses a dirty working tree, an existing `--out` directory,
sensitive-looking files (`.env*` other than `.env.example`, dumps, keys) and
any gitleaks finding not listed in `.gitleaksignore`. `--repo` points every
link (README, docs, issue templates, `package.json`) at the
public repository. Pass `--exclude <path>` to leave something out. It never
pushes; it prints the two commands to do so.

After the first publish the two histories are unrelated, so pick one place
to work. The simplest is to make the public repository the one everybody
clones and commits to from then on, and archive the private one. Keeping both
means re-running `release:prepare` for every release and opening a pull
request from the new tree into the public repository.

AgentSDR took the first route at 0.1.0: the public repository is the only
one worked in and deployed from, and the private one is archived. Its
history is never published or merged in.

## Security fixes

Fix in a private advisory branch, release a patch version, then publish the
advisory. Follow `SECURITY.md`.
