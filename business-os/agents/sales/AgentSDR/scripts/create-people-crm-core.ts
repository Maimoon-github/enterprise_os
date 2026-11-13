/**
 * Creates the additive CRM person/state core.
 *
 * Apply manually with:
 *   bun run scripts/create-people-crm-core.ts --apply
 *
 * This migration does not read, map, migrate, or seed retired CRM data. Manual
 * imports only create/reuse people; a CRM record is created by inbound-reply
 * ingestion in the application.
 */
import { Client } from "pg";

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS crm_person_contact_policies (
  person_id uuid PRIMARY KEY,
  do_not_contact boolean NOT NULL DEFAULT false,
  reason text,
  source text,
  set_at timestamptz,
  cleared_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_person_contact_policies_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT crm_person_contact_policies_source_chk CHECK (
    source IS NULL OR source IN ('human', 'integration', 'inbound_request')
  ),
  CONSTRAINT crm_person_contact_policies_reason_chk CHECK (
    reason IS NULL OR length(btrim(reason)) > 0
  ),
  CONSTRAINT crm_person_contact_policies_timestamp_chk CHECK (
    set_at IS NULL OR cleared_at IS NULL OR cleared_at >= set_at
  ),
  CONSTRAINT crm_person_contact_policies_state_chk CHECK (
    (do_not_contact IS TRUE AND source IS NOT NULL AND set_at IS NOT NULL AND cleared_at IS NULL)
    OR (do_not_contact IS FALSE AND source IS NOT NULL AND set_at IS NOT NULL AND cleared_at IS NOT NULL)
    OR (do_not_contact IS FALSE AND source IS NULL AND set_at IS NULL AND cleared_at IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS crm_person_contact_policies_updated_idx
  ON crm_person_contact_policies (updated_at);

CREATE TABLE IF NOT EXISTS crm_identity_exceptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL,
  account_ref text NOT NULL,
  source_event_key text NOT NULL,
  identity_value text,
  reason text NOT NULL,
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'open',
  resolved_person_id uuid,
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_identity_exceptions_person_fk
    FOREIGN KEY (resolved_person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT crm_identity_exceptions_event_uq UNIQUE (channel, account_ref, source_event_key),
  CONSTRAINT crm_identity_exceptions_channel_chk CHECK (channel IN ('email', 'linkedin')),
  CONSTRAINT crm_identity_exceptions_status_chk CHECK (status IN ('open', 'resolved', 'ignored')),
  CONSTRAINT crm_identity_exceptions_reason_chk CHECK (length(btrim(reason)) > 0),
  CONSTRAINT crm_identity_exceptions_resolution_chk CHECK (
    (status = 'open' AND resolved_person_id IS NULL AND resolved_at IS NULL)
    OR (status = 'resolved' AND resolved_person_id IS NOT NULL AND resolved_at IS NOT NULL)
    OR (status = 'ignored' AND resolved_person_id IS NULL AND resolved_at IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS crm_identity_exceptions_status_created_idx
  ON crm_identity_exceptions (status, created_at);

CREATE TABLE IF NOT EXISTS crm_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL,
  pipeline_id uuid NOT NULL,
  category_key text,
  subcategory_id uuid,
  workflow_state text NOT NULL DEFAULT 'unclassified',
  category_source text,
  category_locked boolean NOT NULL DEFAULT false,
  active_channel text,
  latest_inbound_message_id uuid,
  context_version integer NOT NULL DEFAULT 0,
  last_inbound_at timestamptz,
  last_outbound_at timestamptz,
  last_interaction_at timestamptz,
  next_action_at timestamptz,
  closed_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_records_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT crm_records_pipeline_fk
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id) ON DELETE RESTRICT,
  CONSTRAINT crm_records_category_fk
    FOREIGN KEY (category_key) REFERENCES crm_categories(key) ON DELETE RESTRICT,
  CONSTRAINT crm_records_person_pipeline_uq UNIQUE (person_id, pipeline_id),
  CONSTRAINT crm_records_id_person_uq UNIQUE (id, person_id),
  CONSTRAINT crm_records_id_pipeline_uq UNIQUE (id, pipeline_id),
  CONSTRAINT crm_records_subcategory_target_fk
    FOREIGN KEY (subcategory_id, pipeline_id, category_key)
    REFERENCES crm_subcategories(id, pipeline_id, category_key) ON DELETE RESTRICT,
  CONSTRAINT crm_records_workflow_state_chk CHECK (
    workflow_state IN ('unclassified', 'classifying', 'action_required', 'waiting', 'idle', 'paused', 'closed', 'error')
  ),
  CONSTRAINT crm_records_category_source_chk CHECK (
    category_source IS NULL OR category_source IN ('ai', 'human', 'integration')
  ),
  CONSTRAINT crm_records_active_channel_chk CHECK (
    active_channel IS NULL OR active_channel IN ('email', 'linkedin')
  ),
  CONSTRAINT crm_records_context_version_chk CHECK (context_version >= 0),
  CONSTRAINT crm_records_subcategory_category_chk CHECK (
    subcategory_id IS NULL OR category_key IS NOT NULL
  ),
  CONSTRAINT crm_records_category_source_presence_chk CHECK (
    (category_key IS NULL) = (category_source IS NULL)
  ),
  CONSTRAINT crm_records_category_lock_chk CHECK (
    category_locked IS FALSE OR category_key IS NOT DISTINCT FROM 'customer'
  ),
  CONSTRAINT crm_records_closed_reason_chk CHECK (
    closed_reason IS NULL OR length(btrim(closed_reason)) > 0
  )
);
CREATE INDEX IF NOT EXISTS crm_records_pipeline_state_idx
  ON crm_records (pipeline_id, workflow_state);
CREATE INDEX IF NOT EXISTS crm_records_person_idx ON crm_records (person_id);

CREATE TABLE IF NOT EXISTS crm_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crm_record_id uuid NOT NULL,
  person_id uuid NOT NULL,
  channel text NOT NULL,
  account_ref text NOT NULL,
  provider_thread_id text,
  provider_contact_id text,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_conversations_record_person_fk
    FOREIGN KEY (crm_record_id, person_id)
    REFERENCES crm_records(id, person_id) ON DELETE RESTRICT,
  CONSTRAINT crm_conversations_id_person_channel_account_uq
    UNIQUE (id, person_id, channel, account_ref),
  CONSTRAINT crm_conversations_channel_chk CHECK (channel IN ('email', 'linkedin')),
  CONSTRAINT crm_conversations_status_chk CHECK (status IN ('active', 'closed')),
  CONSTRAINT crm_conversations_account_ref_chk CHECK (length(btrim(account_ref)) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_conversations_provider_thread_uq
  ON crm_conversations (channel, account_ref, provider_thread_id)
  WHERE provider_thread_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS crm_conversations_record_idx ON crm_conversations (crm_record_id);

CREATE OR REPLACE FUNCTION crm_conversations_immutable_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD.id IS DISTINCT FROM NEW.id
     OR OLD.crm_record_id IS DISTINCT FROM NEW.crm_record_id
     OR OLD.person_id IS DISTINCT FROM NEW.person_id
     OR OLD.channel IS DISTINCT FROM NEW.channel
     OR OLD.account_ref IS DISTINCT FROM NEW.account_ref THEN
    RAISE EXCEPTION
      'crm_conversations id, crm_record_id, person_id, channel, and account_ref are immutable'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_conversations_immutable_identity_trg ON crm_conversations;
CREATE TRIGGER crm_conversations_immutable_identity_trg
  BEFORE UPDATE ON crm_conversations
  FOR EACH ROW EXECUTE FUNCTION crm_conversations_immutable_identity();

CREATE TABLE IF NOT EXISTS crm_conversation_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL,
  person_id uuid NOT NULL,
  channel text NOT NULL,
  account_ref text NOT NULL,
  direction text NOT NULL,
  idempotency_key text NOT NULL,
  provider_message_id text,
  subject text,
  body_text text NOT NULL,
  body_html text,
  raw jsonb,
  sent_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_conversation_messages_conversation_identity_fk
    FOREIGN KEY (conversation_id, person_id, channel, account_ref)
    REFERENCES crm_conversations(id, person_id, channel, account_ref) ON DELETE RESTRICT,
  CONSTRAINT crm_conversation_messages_channel_account_idempotency_uq
    UNIQUE (channel, account_ref, idempotency_key),
  CONSTRAINT crm_conversation_messages_channel_chk CHECK (channel IN ('email', 'linkedin')),
  CONSTRAINT crm_conversation_messages_direction_chk CHECK (direction IN ('inbound', 'outbound')),
  CONSTRAINT crm_conversation_messages_idempotency_chk CHECK (length(btrim(idempotency_key)) > 0),
  CONSTRAINT crm_conversation_messages_body_chk CHECK (length(btrim(body_text)) > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_conversation_messages_provider_id_uq
  ON crm_conversation_messages (channel, account_ref, provider_message_id)
  WHERE provider_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS crm_conversation_messages_conversation_idx
  ON crm_conversation_messages (conversation_id, sent_at);

-- Conversation messages are immutable audit records. This also prevents a
-- latest-inbound pointer from being invalidated or changed to outbound data.
CREATE OR REPLACE FUNCTION crm_conversation_messages_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'crm_conversation_messages is append-only; % is not permitted', TG_OP
    USING ERRCODE = 'restrict_violation';
END;
$$;
DROP TRIGGER IF EXISTS crm_conversation_messages_append_only_trg ON crm_conversation_messages;
CREATE TRIGGER crm_conversation_messages_append_only_trg
  BEFORE UPDATE OR DELETE ON crm_conversation_messages
  FOR EACH ROW EXECUTE FUNCTION crm_conversation_messages_append_only();

CREATE OR REPLACE FUNCTION crm_records_validate_latest_inbound()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.latest_inbound_message_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM crm_conversation_messages message
      JOIN crm_conversations conversation ON conversation.id = message.conversation_id
     WHERE message.id = NEW.latest_inbound_message_id
       AND message.direction = 'inbound'
       AND message.person_id = NEW.person_id
       AND conversation.crm_record_id = NEW.id
  ) THEN
    RAISE EXCEPTION
      'latest_inbound_message_id must reference an inbound message for this CRM record'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_records_validate_latest_inbound_trg ON crm_records;
CREATE TRIGGER crm_records_validate_latest_inbound_trg
  BEFORE INSERT OR UPDATE OF latest_inbound_message_id ON crm_records
  FOR EACH ROW EXECUTE FUNCTION crm_records_validate_latest_inbound();

CREATE TABLE IF NOT EXISTS crm_classifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crm_record_id uuid NOT NULL,
  message_id uuid NOT NULL,
  expected_context_version integer NOT NULL,
  previous_category_key text,
  previous_subcategory_id uuid,
  proposed_category_key text,
  proposed_subcategory_id uuid,
  applied_category_key text,
  applied_subcategory_id uuid,
  confidence numeric(5,4),
  reasoning text,
  status text NOT NULL,
  provider text,
  model text,
  request jsonb,
  response jsonb,
  error text,
  acknowledged_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_classifications_record_fk
    FOREIGN KEY (crm_record_id) REFERENCES crm_records(id) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_message_fk
    FOREIGN KEY (message_id) REFERENCES crm_conversation_messages(id) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_previous_category_fk
    FOREIGN KEY (previous_category_key) REFERENCES crm_categories(key) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_proposed_category_fk
    FOREIGN KEY (proposed_category_key) REFERENCES crm_categories(key) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_applied_category_fk
    FOREIGN KEY (applied_category_key) REFERENCES crm_categories(key) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_previous_subcategory_fk
    FOREIGN KEY (previous_subcategory_id) REFERENCES crm_subcategories(id) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_proposed_subcategory_fk
    FOREIGN KEY (proposed_subcategory_id) REFERENCES crm_subcategories(id) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_applied_subcategory_fk
    FOREIGN KEY (applied_subcategory_id) REFERENCES crm_subcategories(id) ON DELETE RESTRICT,
  CONSTRAINT crm_classifications_message_context_uq
    UNIQUE (message_id, expected_context_version),
  CONSTRAINT crm_classifications_status_chk CHECK (
    status IN ('proposed', 'auto_applied', 'accepted', 'rejected', 'overridden', 'stale', 'failed')
  ),
  CONSTRAINT crm_classifications_context_version_chk CHECK (expected_context_version >= 0),
  CONSTRAINT crm_classifications_confidence_chk CHECK (
    confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
  ),
  CONSTRAINT crm_classifications_failed_confidence_chk CHECK (
    status = 'failed' OR confidence IS NOT NULL
  )
);
CREATE INDEX IF NOT EXISTS crm_classifications_record_created_idx
  ON crm_classifications (crm_record_id, created_at);

CREATE OR REPLACE FUNCTION crm_classifications_validate_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  record_pipeline_id uuid;
BEGIN
  SELECT pipeline_id INTO record_pipeline_id
    FROM crm_records
   WHERE id = NEW.crm_record_id;

  IF NOT EXISTS (
    SELECT 1
      FROM crm_conversation_messages message
      JOIN crm_conversations conversation ON conversation.id = message.conversation_id
     WHERE message.id = NEW.message_id
       AND message.direction = 'inbound'
       AND conversation.crm_record_id = NEW.crm_record_id
  ) THEN
    RAISE EXCEPTION 'classification message must be inbound and belong to its CRM record'
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.previous_subcategory_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_subcategories
     WHERE id = NEW.previous_subcategory_id
       AND pipeline_id = record_pipeline_id
       AND category_key = NEW.previous_category_key
  ) THEN
    RAISE EXCEPTION 'previous classification subcategory does not match its category and pipeline'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.proposed_subcategory_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_subcategories
     WHERE id = NEW.proposed_subcategory_id
       AND pipeline_id = record_pipeline_id
       AND category_key = NEW.proposed_category_key
  ) THEN
    RAISE EXCEPTION 'proposed classification subcategory does not match its category and pipeline'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.applied_subcategory_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_subcategories
     WHERE id = NEW.applied_subcategory_id
       AND pipeline_id = record_pipeline_id
       AND category_key = NEW.applied_category_key
  ) THEN
    RAISE EXCEPTION 'applied classification subcategory does not match its category and pipeline'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_classifications_validate_scope_trg ON crm_classifications;
CREATE TRIGGER crm_classifications_validate_scope_trg
  BEFORE INSERT OR UPDATE ON crm_classifications
  FOR EACH ROW EXECUTE FUNCTION crm_classifications_validate_scope();

CREATE TABLE IF NOT EXISTS crm_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL,
  crm_record_id uuid,
  pipeline_id uuid,
  event_type text NOT NULL,
  actor_type text NOT NULL,
  actor_ref text,
  from_data jsonb,
  to_data jsonb,
  meta jsonb,
  context_version integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_events_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT crm_events_record_person_fk
    FOREIGN KEY (crm_record_id, person_id)
    REFERENCES crm_records(id, person_id) ON DELETE RESTRICT,
  CONSTRAINT crm_events_record_pipeline_fk
    FOREIGN KEY (crm_record_id, pipeline_id)
    REFERENCES crm_records(id, pipeline_id) ON DELETE RESTRICT,
  CONSTRAINT crm_events_pipeline_fk
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id) ON DELETE RESTRICT,
  CONSTRAINT crm_events_event_type_chk CHECK (length(btrim(event_type)) > 0),
  CONSTRAINT crm_events_actor_type_chk CHECK (
    actor_type IN ('ai', 'human', 'system', 'integration', 'authenticated_operator')
  ),
  CONSTRAINT crm_events_context_version_chk CHECK (
    context_version IS NULL OR context_version >= 0
  ),
  CONSTRAINT crm_events_record_scope_chk CHECK (
    (crm_record_id IS NULL AND pipeline_id IS NULL)
    OR (crm_record_id IS NOT NULL AND pipeline_id IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS crm_events_person_created_idx ON crm_events (person_id, created_at);
CREATE INDEX IF NOT EXISTS crm_events_record_created_idx ON crm_events (crm_record_id, created_at);

CREATE OR REPLACE FUNCTION crm_events_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'crm_events is append-only; % is not permitted', TG_OP
    USING ERRCODE = 'restrict_violation';
END;
$$;
DROP TRIGGER IF EXISTS crm_events_append_only_trg ON crm_events;
CREATE TRIGGER crm_events_append_only_trg
  BEFORE UPDATE OR DELETE ON crm_events
  FOR EACH ROW EXECUTE FUNCTION crm_events_append_only();
`;

const EXPECTED_TABLES = [
  "crm_classifications",
  "crm_conversation_messages",
  "crm_conversations",
  "crm_events",
  "crm_identity_exceptions",
  "crm_person_contact_policies",
  "crm_records",
] as const;
const EXPECTED_CONSTRAINTS = [
  "crm_conversations_record_person_fk",
  "crm_conversation_messages_conversation_identity_fk",
  "crm_classifications_message_context_uq",
  "crm_events_record_person_fk",
  "crm_events_record_pipeline_fk",
] as const;
const EXPECTED_TRIGGERS = [
  "crm_classifications_validate_scope_trg",
  "crm_conversations_immutable_identity_trg",
  "crm_conversation_messages_append_only_trg",
  "crm_events_append_only_trg",
  "crm_records_validate_latest_inbound_trg",
] as const;

async function main(): Promise<void> {
  if (!process.argv.includes("--apply")) {
    throw new Error("Refusing to modify the database without --apply.");
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
      const { rows } = await client.query<{ table_name: string }>(
        `SELECT table_name
           FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = ANY($1::text[])
          ORDER BY table_name`,
        [EXPECTED_TABLES],
      );
      const actual = rows.map((row) => row.table_name);
      if (actual.length !== EXPECTED_TABLES.length || actual.some((name, i) => name !== EXPECTED_TABLES[i])) {
        throw new Error(`CRM core table verification failed: ${JSON.stringify(actual)}`);
      }

      const { rows: constraintRows } = await client.query<{ n: string }>(
        `SELECT count(*)::text AS n
           FROM pg_constraint
          WHERE conname = ANY($1::text[])`,
        [EXPECTED_CONSTRAINTS],
      );
      if (constraintRows[0]?.n !== String(EXPECTED_CONSTRAINTS.length)) {
        throw new Error("CRM core expected constraint verification failed");
      }
      const { rows: triggerRows } = await client.query<{ n: string }>(
        `SELECT count(*)::text AS n
           FROM pg_trigger
          WHERE tgname = ANY($1::text[])
            AND NOT tgisinternal`,
        [EXPECTED_TRIGGERS],
      );
      if (triggerRows[0]?.n !== String(EXPECTED_TRIGGERS.length)) {
        throw new Error("CRM core trigger verification failed");
      }

      await client.query("COMMIT");
      console.log(`CRM core ready: tables=${actual.length}`);
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
