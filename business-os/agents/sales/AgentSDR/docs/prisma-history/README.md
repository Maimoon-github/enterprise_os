# Prisma migration history (archived)

Nothing here runs. It is kept as the written record of how the 11 LinkedIn
tables were built, in the same spirit as `scripts/` for the Drizzle side.

Those tables originally belonged to `linkedin-automation-next`, which was
merged into this app and used Prisma. The app is now entirely on Drizzle —
the live tables are described by `src/lib/linkedin/schema.ts`, which was
written by introspecting the database, not by transcribing `schema.prisma`.

## Why keep it

- `migrations/` is the only ordered account of how those tables reached their
  current shape — 33 migrations from the initial schema through the search
  queue and follow-up-3 additions.
- `schema.prisma` records the relations and cascade rules that the live
  foreign keys still enforce. `src/lib/linkedin/schema.ts` deliberately does
  not redeclare those relations, so this is where to look for them.

## Do not

- Do not run `prisma migrate`, `db push`, or anything else against the live
  database. The Prisma CLI and client are no longer dependencies, and the
  guard script that used to block the dangerous commands is gone with them.
- Do not treat `schema.prisma` as current. It had already drifted from the
  database before the migration: `LeadStatus` and `MessageType` list
  `FOLLOW_UP_3_SENT` / `COMPLETED` / `FOLLOW_UP_3` mid-enum, while the live
  types have them appended at the end. Postgres enum order is part of the
  type, so `src/lib/linkedin/schema.ts` follows the database.

## Schema changes from here

Same rule as the rest of this app: write a one-shot migration in `scripts/`,
run it by hand against the live database, and update the matching Drizzle
table in `src/lib/linkedin/schema.ts`.

Note that the LinkedIn tables are deliberately **not** in
`drizzle.config.ts`'s `OWNED_TABLES`, so `drizzle-kit` will not diff or manage
them — that is what keeps `drizzle-kit push` from ever touching live LinkedIn
data.
