/**
 * Creates the lead database — people, companies, and the column registry.
 *
 * Apply additive preparation with:
 *   bun run scripts/create-lead-tables.ts --apply
 *
 * This script deliberately does not create People/campaign uniqueness
 * constraints or make campaign Person references mandatory. The webhook inbox
 * key is safe to add here because every legacy row keeps a null key. Run
 * scripts/finalize-lead-tables.ts only after cleanup, backfill, and preflight.
 *
 * Bun loads .env.local automatically, which is why this file has none of the
 * hand-rolled dotenv parsing the older scripts/*.js migrations carry.
 *
 * Every statement is guarded so re-running is safe. Keep in sync with
 * src/lib/leads/schema.ts.
 *
 * ---------------------------------------------------------------------------
 * WHY THESE TABLES ARE NOT IN OWNED_TABLES
 * ---------------------------------------------------------------------------
 * CLAUDE.md says every new snake_case table goes into the OWNED_TABLES
 * allowlist in drizzle.config.ts. These four are a deliberate exception.
 *
 * HISTORICAL NOTE: `people` and `companies` used to gain columns at RUNTIME
 * (ALTER TABLE ... ADD COLUMN from the settings UI). That path is gone: custom
 * fields are now keys in `custom` jsonb, defined per organization in
 * entity_columns (see src/lib/leads/columns.ts), and the core registry rows
 * below are created per organization lazily. This script only ever seeded the
 * first organization's copy. The tables stay out of OWNED_TABLES for the
 * remaining reasons: they are hand-maintained through scripts/.
 *
 * `entity_columns` and `import_runs` have fixed schemas and could safely be
 * managed, but they are excluded too so the rule stays one sentence: the lead
 * database is hand-maintained through scripts/, the same as the LinkedIn
 * tables. A rule with an exception inside it is a rule someone will get wrong.
 */
import { Client } from "pg";

const SQL = `
-- ---------------------------------------------------------------------------
-- companies
-- ---------------------------------------------------------------------------
-- Identity is the normalized domain. Everything else is optional, because an
-- enriched list often knows a domain and little more on first import.
CREATE TABLE IF NOT EXISTS companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain text NOT NULL UNIQUE,
  name text,
  linkedin_url text,
  -- Import columns the user chose not to map. Kept rather than dropped so a
  -- mis-mapped import is recoverable without re-uploading the file.
  raw jsonb NOT NULL DEFAULT '{}',
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS companies_name_idx ON companies (lower(name));

-- ---------------------------------------------------------------------------
-- people
-- ---------------------------------------------------------------------------
-- company_id is NULLABLE on purpose. A person imported from a LinkedIn list
-- usually has no resolvable domain, and a person with no company is still a
-- person worth storing.
CREATE TABLE IF NOT EXISTS people (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text,
  -- Normalized to the bare slug ("janedoe42"), never a full URL. This is
  -- the format "Lead".linkedinUrl already uses on 100% of its rows.
  linkedin_url text,
  first_name text,
  last_name text,
  full_name text,
  title text,
  -- Signed media.licdn.com URL. Lives on the person, not the campaign Lead,
  -- so the CRM and the people table can show it without a LinkedIn join.
  profile_picture_url text,
  company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
  raw jsonb NOT NULL DEFAULT '{}',
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- A LinkedIn campaign may create a provisional Person before Unipile reveals
-- the canonical public identifier. The campaign Lead is the temporary identity
-- bridge during that short state, so People itself cannot require email/URL.
ALTER TABLE people DROP CONSTRAINT IF EXISTS people_identity_chk;
-- Added after the table shipped; scripts/add-people-profile-picture.ts backfills it.
ALTER TABLE people ADD COLUMN IF NOT EXISTS profile_picture_url text;
-- E.164, dialed by the WhatsApp Call button. scripts/add-people-phone.ts.
ALTER TABLE people ADD COLUMN IF NOT EXISTS phone text;
CREATE INDEX IF NOT EXISTS people_phone_lookup_idx ON people (phone) WHERE phone IS NOT NULL;

CREATE INDEX IF NOT EXISTS people_company_idx ON people (company_id);
CREATE INDEX IF NOT EXISTS people_name_idx    ON people (lower(full_name));
CREATE INDEX IF NOT EXISTS people_created_idx ON people (created_at DESC);
-- Non-unique lookup indexes keep the restart-safe backfill linear. Finalize
-- replaces the identity guarantees with unique indexes after audits pass.
CREATE INDEX IF NOT EXISTS people_email_lookup_idx ON people (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS people_linkedin_lookup_idx ON people (linkedin_url) WHERE linkedin_url IS NOT NULL;

-- Direct People references start nullable only so schema preparation can run
-- before the backfill. Both become mandatory before application deployment.
ALTER TABLE outreach_leads ADD COLUMN IF NOT EXISTS person_id uuid;
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "personId" uuid;
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "sourceLinkedinIdentifier" text;
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "sourceLinkedinApi" text;
ALTER TYPE "LeadStatus" ADD VALUE IF NOT EXISTS 'CANCELLED';
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "resolveRetryCount" integer NOT NULL DEFAULT 0;
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "resolveNextAttemptAt" timestamp(3);
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "resolveLastError" text;
ALTER TABLE "Lead" ADD COLUMN IF NOT EXISTS "supersededByLeadId" text;
ALTER TABLE "Message" ADD COLUMN IF NOT EXISTS "duplicateOfMessageId" text;
ALTER TABLE "SearchResult" ADD COLUMN IF NOT EXISTS "sourceLinkedinApi" text;
ALTER TABLE "Campaign" ADD COLUMN IF NOT EXISTS "invitationMessage" text;
ALTER TABLE "Campaign" ADD COLUMN IF NOT EXISTS "acceptanceMessage" text;
ALTER TABLE "Campaign" ADD COLUMN IF NOT EXISTS "followUp1Message" text;
ALTER TABLE "Campaign" ADD COLUMN IF NOT EXISTS "followUp2Message" text;
ALTER TABLE "Campaign" ADD COLUMN IF NOT EXISTS "followUp3Message" text;
ALTER TABLE "WebhookEvent" ADD COLUMN IF NOT EXISTS "providerEventKey" text;
ALTER TABLE "WebhookEvent" ADD COLUMN IF NOT EXISTS "processingAttempt" integer NOT NULL DEFAULT 0;
ALTER TABLE "WebhookEvent" ADD COLUMN IF NOT EXISTS "processingStartedAt" timestamp(3);
ALTER TABLE "WebhookEvent" ADD COLUMN IF NOT EXISTS "nextAttemptAt" timestamp(3);
ALTER TABLE "WebhookEvent" ADD COLUMN IF NOT EXISTS "processedAt" timestamp(3);
CREATE INDEX IF NOT EXISTS outreach_leads_person_idx ON outreach_leads (person_id);
CREATE INDEX IF NOT EXISTS lead_person_idx ON "Lead" ("personId");
CREATE INDEX IF NOT EXISTS "Lead_supersededByLeadId_idx" ON "Lead" ("supersededByLeadId");
CREATE INDEX IF NOT EXISTS "Message_duplicateOfMessageId_idx" ON "Message" ("duplicateOfMessageId");
CREATE INDEX IF NOT EXISTS "Message_leadId_idx" ON "Message" ("leadId") WHERE "leadId" IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS "WebhookEvent_providerEventKey_uq"
  ON "WebhookEvent" ("providerEventKey") WHERE "providerEventKey" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "WebhookEvent_retry_idx"
  ON "WebhookEvent" ("processingStatus", "nextAttemptAt", "createdAt");
CREATE INDEX IF NOT EXISTS "Lead_unresolvedLinkedin_idx"
  ON "Lead" ("sourceLinkedinIdentifier", "createdAt")
  WHERE "sourceLinkedinIdentifier" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "Lead_unresolvedLinkedin_lookup_idx"
  ON "Lead" (lower("sourceLinkedinIdentifier"), "sourceLinkedinApi")
  WHERE "sourceLinkedinIdentifier" IS NOT NULL AND "personId" IS NOT NULL;

DO $$ BEGIN
  ALTER TABLE outreach_leads ADD CONSTRAINT outreach_leads_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE "Lead" ADD CONSTRAINT "Lead_personId_fkey"
    FOREIGN KEY ("personId") REFERENCES people(id) ON DELETE RESTRICT NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- entity_columns — the column registry
-- ---------------------------------------------------------------------------
-- NOT storage: the data lives in real columns on people/companies. This is the
-- authoritative catalog of what the application believes exists, and it does
-- three jobs no physical column can:
--   1. Injection defense. User columns are unknown to Drizzle's static types,
--      so queries build identifiers at runtime. A name reaches SQL only after
--      matching a row here.
--   2. Display metadata. name/type/config have no physical equivalent.
--   3. Schema history. These tables are outside OWNED_TABLES, so this table
--      plus scripts/ IS the migration record.
CREATE TABLE IF NOT EXISTS entity_columns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 'person' | 'company'
  entity text NOT NULL,
  -- The PHYSICAL Postgres column name. Generated, never user-supplied, and
  -- never changed after creation -- that is what makes a rename free.
  key text NOT NULL,
  -- The display label. Freely renameable; touches this row and nothing else.
  name text NOT NULL,
  -- UI type from src/lib/grid/types.ts ColumnType, so the grid and the lead
  -- tables speak one vocabulary.
  type text NOT NULL,
  -- Physical type actually used in the ALTER TABLE. Restricted set -- see
  -- PG_TYPE_FOR_COLUMN_TYPE in src/lib/leads/types.ts.
  pg_type text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}',
  -- Core columns ship with the table and cannot be dropped or retyped.
  is_core boolean NOT NULL DEFAULT false,
  position double precision NOT NULL,
  -- Soft delete. The column disappears from UI, mapping and queries but keeps
  -- its data; a physical DROP COLUMN is a separate, explicit act.
  archived_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT entity_columns_entity_key_uq UNIQUE (entity, key)
);

CREATE INDEX IF NOT EXISTS entity_columns_entity_pos_idx
  ON entity_columns (entity, position) WHERE archived_at IS NULL;

-- ---------------------------------------------------------------------------
-- import_runs
-- ---------------------------------------------------------------------------
-- Audit and replay. Storing the exact mapping means the second import of the
-- same list is one click, and a bad import is diagnosable after the fact.
CREATE TABLE IF NOT EXISTS import_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 'grid' | 'file'
  source text NOT NULL,
  grid_table_id uuid REFERENCES grid_tables(id) ON DELETE SET NULL,
  filename text,
  -- 'database' | 'campaign'
  destination text NOT NULL,
  -- UUID (email) or cuid/text (LinkedIn); kept as text so both channels fit.
  destination_campaign_id text,
  mapping jsonb NOT NULL,
  stats jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE import_runs ADD COLUMN IF NOT EXISTS destination_campaign_id text;

CREATE INDEX IF NOT EXISTS import_runs_created_idx ON import_runs (created_at DESC);
`;

/**
 * Core columns, seeded as registry rows so the settings UI, the mapping
 * catalog and the query builder all read ONE list and none of them needs to
 * know which columns are core.
 *
 * `people.company_id` is deliberately absent: it is a relation, not a
 * mappable field. The importer derives it from the company's domain, and the
 * table view renders it as a link rather than a value.
 */
const CORE_COLUMNS: {
  entity: "person" | "company";
  key: string;
  name: string;
  type: string;
  pgType: string;
}[] = [
  { entity: "company", key: "domain", name: "Domain", type: "url", pgType: "text" },
  { entity: "company", key: "name", name: "Company Name", type: "text", pgType: "text" },
  { entity: "company", key: "linkedin_url", name: "Company LinkedIn", type: "url", pgType: "text" },

  { entity: "person", key: "email", name: "Email", type: "email", pgType: "text" },
  { entity: "person", key: "linkedin_url", name: "LinkedIn URL", type: "url", pgType: "text" },
  { entity: "person", key: "first_name", name: "First Name", type: "text", pgType: "text" },
  { entity: "person", key: "last_name", name: "Last Name", type: "text", pgType: "text" },
  { entity: "person", key: "full_name", name: "Full Name", type: "text", pgType: "text" },
  { entity: "person", key: "title", name: "Job Title", type: "text", pgType: "text" },
  { entity: "person", key: "profile_picture_url", name: "Profile Picture", type: "image", pgType: "text" },
  { entity: "person", key: "phone", name: "Phone", type: "text", pgType: "text" },
];

async function main() {
  if (!process.argv.includes("--apply")) {
    throw new Error(
      "Refusing to modify the database without --apply. This command performs additive schema preparation only.",
    );
  }
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set — check .env.local");
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });

  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    await client.query(SQL);

    // UPSERT, per the scripts/ convention: re-running must not clobber a
    // label the user has since renamed, so only position and is_core are
    // refreshed. DO UPDATE rather than DO NOTHING so is_core can be repaired
    // if a core column was somehow registered without it.
    for (const [i, column] of CORE_COLUMNS.entries()) {
      await client.query(
        `INSERT INTO entity_columns (entity, key, name, type, pg_type, is_core, position)
         VALUES ($1, $2, $3, $4, $5, true, $6)
         ON CONFLICT (entity, key) DO UPDATE
           SET is_core = true, position = EXCLUDED.position, updated_at = now()`,
        [column.entity, column.key, column.name, column.type, column.pgType, i + 1],
      );
    }

    const { rows: tables } = await client.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables
       WHERE table_schema = 'public'
         AND table_name IN ('people','companies','entity_columns','import_runs')
       ORDER BY table_name`,
    );
    const { rows: counts } = await client.query<{ entity: string; n: string }>(
      `SELECT entity, count(*)::text AS n FROM entity_columns GROUP BY entity ORDER BY entity`,
    );

    console.log("lead tables present:", tables.map((r) => r.table_name).join(", "));
    console.log("registered columns:", counts.map((r) => `${r.entity}=${r.n}`).join(" "));
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
