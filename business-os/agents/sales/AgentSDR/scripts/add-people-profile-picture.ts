/**
 * Adds people.profile_picture_url and fills it from wherever a picture was
 * already sitting.
 *
 * Run with:  bun run scripts/add-people-profile-picture.ts
 *
 * Until now the mapping dialog offered "Profile picture URL" as a person
 * field, but the importer only kept it in people.raw and on the campaign
 * "Lead" row, so the people table itself never had it. This registers the
 * column as core (matching the CORE_COLUMNS entry in create-lead-tables.ts,
 * which scripts/check-lead-column-drift.ts enforces) and backfills, in order
 * of preference: what the import put in raw, then the newest "Lead" for the
 * person, then the "Connection" snapshot from the acceptance webhook.
 *
 * Re-runnable: the column and registry row are guarded, and the backfill
 * only touches rows still NULL.
 */
import { Client } from "pg";

const SQL = `
ALTER TABLE people ADD COLUMN IF NOT EXISTS profile_picture_url text;

INSERT INTO entity_columns (entity, key, name, type, pg_type, is_core, position)
VALUES ('person', 'profile_picture_url', 'Profile Picture', 'image', 'text', true,
        (SELECT coalesce(max(position), 0) + 1 FROM entity_columns WHERE entity = 'person'))
ON CONFLICT (entity, key) DO UPDATE SET is_core = true, updated_at = now();

UPDATE people p
   SET profile_picture_url = nullif(trim(p.raw->>'profilePictureUrl'), ''),
       updated_at = now()
 WHERE p.profile_picture_url IS NULL
   AND nullif(trim(p.raw->>'profilePictureUrl'), '') IS NOT NULL;

UPDATE people p
   SET profile_picture_url = l.url, updated_at = now()
  FROM (
    SELECT DISTINCT ON ("personId") "personId", "profilePictureUrl" AS url
      FROM "Lead"
     WHERE "profilePictureUrl" IS NOT NULL
     ORDER BY "personId", "updatedAt" DESC
  ) l
 WHERE p.id = l."personId" AND p.profile_picture_url IS NULL;

UPDATE people p
   SET profile_picture_url = c.url, updated_at = now()
  FROM (
    SELECT DISTINCT ON (l."personId") l."personId", c."profilePictureUrl" AS url
      FROM "Connection" c JOIN "Lead" l ON l.id = c."leadId"
     WHERE c."profilePictureUrl" IS NOT NULL
     ORDER BY l."personId", c."updatedAt" DESC
  ) c
 WHERE p.id = c."personId" AND p.profile_picture_url IS NULL;
`;

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    await client.query(SQL);
    const { rows } = await client.query<{ total: string; with_picture: string }>(
      `SELECT count(*)::text AS total, count(profile_picture_url)::text AS with_picture FROM people`,
    );
    console.log(`people: ${rows[0].with_picture} of ${rows[0].total} have a profile picture`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
