/**
 * Creates the additive CRM configuration foundation.
 *
 * Apply manually with:
 *   bun run scripts/create-people-crm-foundation.ts --apply
 *
 * This migration deliberately does not create or seed any CRM records,
 * subcategories, people, or legacy tables. It is safe to re-run: all DDL is
 * guarded and the two seed sets are UPSERTs.
 */
import { Client } from "pg";

const DEFAULT_PIPELINE_ID = "00000000-0000-0000-0000-000000000001";
const CATEGORY_SEEDS = [
  ["customer", "Customer", 0],
  ["interested", "Interested", 1],
  ["not_interested", "Not Interested", 2],
  ["other", "Other", 3],
] as const;

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS crm_pipelines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  is_default boolean NOT NULL DEFAULT false,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_pipelines_name_uq UNIQUE (name),
  CONSTRAINT crm_pipelines_name_chk CHECK (length(btrim(name)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS crm_pipelines_one_default_uq
  ON crm_pipelines (is_default) WHERE is_default IS TRUE;

CREATE TABLE IF NOT EXISTS crm_categories (
  key text PRIMARY KEY,
  label text NOT NULL,
  sort_order integer NOT NULL,
  is_system boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_categories_label_uq UNIQUE (label),
  CONSTRAINT crm_categories_sort_order_uq UNIQUE (sort_order),
  CONSTRAINT crm_categories_key_chk CHECK (
    key IN ('customer', 'interested', 'not_interested', 'other')
  ),
  CONSTRAINT crm_categories_label_chk CHECK (length(btrim(label)) > 0),
  CONSTRAINT crm_categories_is_system_chk CHECK (is_system IS TRUE)
);

CREATE TABLE IF NOT EXISTS crm_subcategories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id uuid NOT NULL,
  category_key text NOT NULL,
  key text NOT NULL,
  name text NOT NULL,
  description text,
  classification_guidance text,
  active boolean NOT NULL DEFAULT true,
  review_required boolean NOT NULL DEFAULT false,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_subcategories_pipeline_fk
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id) ON DELETE RESTRICT,
  CONSTRAINT crm_subcategories_category_fk
    FOREIGN KEY (category_key) REFERENCES crm_categories(key) ON DELETE RESTRICT,
  CONSTRAINT crm_subcategories_pipeline_key_uq UNIQUE (pipeline_id, key),
  CONSTRAINT crm_subcategories_target_uq UNIQUE (id, pipeline_id, category_key),
  CONSTRAINT crm_subcategories_key_chk CHECK (key ~ '^[a-z][a-z0-9_]*$'),
  CONSTRAINT crm_subcategories_name_chk CHECK (length(btrim(name)) > 0),
  CONSTRAINT crm_subcategories_sort_order_chk CHECK (sort_order >= 0)
);

CREATE INDEX IF NOT EXISTS crm_subcategories_pipeline_category_idx
  ON crm_subcategories (pipeline_id, category_key);

CREATE TABLE IF NOT EXISTS crm_settings (
  pipeline_id uuid PRIMARY KEY,
  auto_apply_confidence numeric(4,3) NOT NULL DEFAULT 0.85,
  review_other boolean NOT NULL DEFAULT true,
  customer_requires_review boolean NOT NULL DEFAULT true,
  human_send_only boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_settings_pipeline_fk
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id) ON DELETE RESTRICT,
  CONSTRAINT crm_settings_confidence_chk
    CHECK (auto_apply_confidence >= 0 AND auto_apply_confidence <= 1),
  CONSTRAINT crm_settings_customer_review_chk CHECK (customer_requires_review IS TRUE),
  CONSTRAINT crm_settings_human_send_only_chk CHECK (human_send_only IS TRUE)
);

-- The four top-level categories are product vocabulary, not administrator
-- configuration. Protect them below the API layer as well.
CREATE OR REPLACE FUNCTION crm_categories_protect_system_rows()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'system CRM categories cannot be deleted'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.key IS DISTINCT FROM NEW.key
     OR OLD.label IS DISTINCT FROM NEW.label
     OR OLD.sort_order IS DISTINCT FROM NEW.sort_order
     OR OLD.is_system IS DISTINCT FROM NEW.is_system THEN
    RAISE EXCEPTION 'system CRM categories cannot be changed'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS crm_categories_protect_system_rows_trg ON crm_categories;
CREATE TRIGGER crm_categories_protect_system_rows_trg
  BEFORE UPDATE OR DELETE ON crm_categories
  FOR EACH ROW
  EXECUTE FUNCTION crm_categories_protect_system_rows();

-- Drizzle can describe the invariant but cannot portably express an immutable
-- set of columns. Keep it at the database boundary so every writer obeys it.
CREATE OR REPLACE FUNCTION crm_subcategories_immutable_fields()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.key IS DISTINCT FROM NEW.key
     OR OLD.pipeline_id IS DISTINCT FROM NEW.pipeline_id
     OR OLD.category_key IS DISTINCT FROM NEW.category_key THEN
    RAISE EXCEPTION
      'crm_subcategories key, pipeline_id, and category_key are immutable'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS crm_subcategories_immutable_fields_trg ON crm_subcategories;
CREATE TRIGGER crm_subcategories_immutable_fields_trg
  BEFORE UPDATE ON crm_subcategories
  FOR EACH ROW
  EXECUTE FUNCTION crm_subcategories_immutable_fields();
`;

async function main(): Promise<void> {
  if (!process.argv.includes("--apply")) {
    throw new Error(
      "Refusing to modify the database without --apply. This command creates additive CRM configuration tables.",
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
    await client.query("BEGIN");
    try {
      await client.query(SCHEMA_SQL);

      await client.query(
        `INSERT INTO crm_pipelines (id, name, is_default, active)
         VALUES ($1, 'Default', true, true)
         ON CONFLICT (id) DO UPDATE SET
           name = EXCLUDED.name,
           is_default = EXCLUDED.is_default,
           active = EXCLUDED.active,
           updated_at = now()`,
        [DEFAULT_PIPELINE_ID],
      );

      for (const [key, label, sortOrder] of CATEGORY_SEEDS) {
        await client.query(
          `INSERT INTO crm_categories (key, label, sort_order, is_system)
           VALUES ($1, $2, $3, true)
           ON CONFLICT (key) DO UPDATE SET
             label = EXCLUDED.label,
             sort_order = EXCLUDED.sort_order,
             is_system = true,
             updated_at = now()`,
          [key, label, sortOrder],
        );
      }

      // Settings are user-editable after creation, so a re-run must not reset
      // an administrator's confidence threshold or review preference.
      await client.query(
        `INSERT INTO crm_settings (pipeline_id)
         VALUES ($1)
         ON CONFLICT (pipeline_id) DO NOTHING`,
        [DEFAULT_PIPELINE_ID],
      );

      const { rows: tableRows } = await client.query<{ table_name: string }>(
        `SELECT table_name
           FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name IN ('crm_pipelines', 'crm_categories', 'crm_subcategories', 'crm_settings')
          ORDER BY table_name`,
      );
      const expectedTables = [
        "crm_categories",
        "crm_pipelines",
        "crm_settings",
        "crm_subcategories",
      ];
      if (tableRows.length !== expectedTables.length || tableRows.some((row, i) => row.table_name !== expectedTables[i])) {
        throw new Error(`CRM foundation table verification failed: ${JSON.stringify(tableRows)}`);
      }

      const { rows: pipelineRows } = await client.query<{ n: string }>(
        `SELECT count(*)::text AS n
           FROM crm_pipelines
          WHERE id = $1 AND name = 'Default' AND is_default IS TRUE`,
        [DEFAULT_PIPELINE_ID],
      );
      const { rows: categoryRows } = await client.query<{ n: string }>(
        `SELECT count(*)::text AS n
           FROM crm_categories
          WHERE is_system IS TRUE
            AND key IN ('customer', 'interested', 'not_interested', 'other')`,
      );
      const { rows: subcategoryRows } = await client.query<{ n: string }>(
        "SELECT count(*)::text AS n FROM crm_subcategories",
      );
      const { rows: settingsRows } = await client.query<{ n: string }>(
        "SELECT count(*)::text AS n FROM crm_settings WHERE pipeline_id = $1",
        [DEFAULT_PIPELINE_ID],
      );

      if (pipelineRows[0]?.n !== "1" || categoryRows[0]?.n !== "4") {
        throw new Error(
          `CRM foundation seed verification failed: pipelines=${pipelineRows[0]?.n ?? "?"} categories=${categoryRows[0]?.n ?? "?"}`,
        );
      }
      if (settingsRows[0]?.n !== "1") {
        throw new Error(
          `CRM foundation settings verification failed: settings=${settingsRows[0]?.n ?? "?"}`,
        );
      }

      await client.query("COMMIT");
      console.log(
        `CRM foundation ready: tables=${tableRows.length} default_pipelines=${pipelineRows[0].n} categories=${categoryRows[0].n} subcategories=${subcategoryRows[0].n} settings=${settingsRows[0].n}`,
      );
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }
  } finally {
    await client.end();
  }
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
