/**
 * Creates the additive CRM workflow, sequence, Knowledge, send-audit, and
 * durable-job tables.
 *
 * Apply manually with:
 *   bun run scripts/create-people-crm-workflow.ts --apply
 *
 * The CRM foundation and core migrations must already be applied. This
 * script only manages canonical CRM workflow data and is safe to re-run.
 */
import { Client } from "pg";

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS crm_sequences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  status text NOT NULL DEFAULT 'active',
  draft_version_id uuid NOT NULL,
  latest_published_version_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_sequences_id_draft_version_uq UNIQUE (id, draft_version_id),
  CONSTRAINT crm_sequences_name_chk CHECK (length(btrim(name)) > 0),
  CONSTRAINT crm_sequences_status_chk CHECK (status IN ('active', 'archived'))
);
CREATE INDEX IF NOT EXISTS crm_sequences_status_name_idx ON crm_sequences (status, name);

CREATE TABLE IF NOT EXISTS crm_sequence_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_id uuid NOT NULL,
  version integer NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_sequence_versions_sequence_fk
    FOREIGN KEY (sequence_id) REFERENCES crm_sequences(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_versions_sequence_version_uq UNIQUE (sequence_id, version),
  CONSTRAINT crm_sequence_versions_id_sequence_uq UNIQUE (id, sequence_id),
  CONSTRAINT crm_sequence_versions_version_chk CHECK (version > 0),
  CONSTRAINT crm_sequence_versions_status_chk CHECK (status IN ('draft', 'published')),
  CONSTRAINT crm_sequence_versions_published_at_chk CHECK (
    (status = 'draft' AND published_at IS NULL)
    OR (status = 'published' AND published_at IS NOT NULL)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_sequence_versions_one_draft_uq
  ON crm_sequence_versions (sequence_id) WHERE status = 'draft';

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_sequences_draft_version_id_crm_sequence_versions_id_fk') THEN
    ALTER TABLE crm_sequences ADD CONSTRAINT crm_sequences_draft_version_id_crm_sequence_versions_id_fk
      FOREIGN KEY (draft_version_id) REFERENCES crm_sequence_versions(id)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_sequences_latest_published_version_id_crm_sequence_versions') THEN
    ALTER TABLE crm_sequences ADD CONSTRAINT crm_sequences_latest_published_version_id_crm_sequence_versions_id_fk
      FOREIGN KEY (latest_published_version_id) REFERENCES crm_sequence_versions(id)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS crm_sequence_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_version_id uuid NOT NULL,
  position integer NOT NULL,
  step_type text NOT NULL,
  name text NOT NULL,
  delay_minutes integer NOT NULL,
  subject_template text,
  body_template text,
  ai_instructions text NOT NULL,
  knowledge_tags text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_sequence_steps_version_fk
    FOREIGN KEY (sequence_version_id) REFERENCES crm_sequence_versions(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_steps_version_position_uq UNIQUE (sequence_version_id, position),
  CONSTRAINT crm_sequence_steps_id_version_uq UNIQUE (id, sequence_version_id),
  CONSTRAINT crm_sequence_steps_position_chk CHECK (position > 0),
  CONSTRAINT crm_sequence_steps_delay_chk CHECK (delay_minutes >= 0),
  CONSTRAINT crm_sequence_steps_name_chk CHECK (length(btrim(name)) > 0),
  CONSTRAINT crm_sequence_steps_ai_instructions_chk CHECK (length(btrim(ai_instructions)) > 0),
  CONSTRAINT crm_sequence_steps_semantics_chk CHECK (
    (position = 1 AND step_type = 'reply' AND delay_minutes = 0)
    OR (position > 1 AND step_type = 'follow_up')
  )
);

CREATE TABLE IF NOT EXISTS crm_subcategory_sequence_assignments (
  subcategory_id uuid NOT NULL,
  sequence_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_subcategory_sequence_assignments_pk PRIMARY KEY (subcategory_id),
  CONSTRAINT crm_subcategory_sequence_assignments_subcategory_fk
    FOREIGN KEY (subcategory_id) REFERENCES crm_subcategories(id) ON DELETE RESTRICT,
  CONSTRAINT crm_subcategory_sequence_assignments_sequence_fk
    FOREIGN KEY (sequence_id) REFERENCES crm_sequences(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS crm_subcategory_sequence_assignments_sequence_idx
  ON crm_subcategory_sequence_assignments (sequence_id);

CREATE TABLE IF NOT EXISTS crm_record_sequence_overrides (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crm_record_id uuid NOT NULL,
  sequence_id uuid NOT NULL,
  source text NOT NULL,
  effective_at timestamptz NOT NULL DEFAULT now(),
  cleared_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_record_sequence_overrides_record_fk
    FOREIGN KEY (crm_record_id) REFERENCES crm_records(id) ON DELETE RESTRICT,
  CONSTRAINT crm_record_sequence_overrides_sequence_fk
    FOREIGN KEY (sequence_id) REFERENCES crm_sequences(id) ON DELETE RESTRICT,
  CONSTRAINT crm_record_sequence_overrides_source_chk CHECK (source IN ('human', 'integration')),
  CONSTRAINT crm_record_sequence_overrides_time_chk
    CHECK (cleared_at IS NULL OR cleared_at >= effective_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_record_sequence_overrides_active_uq
  ON crm_record_sequence_overrides (crm_record_id) WHERE cleared_at IS NULL;
CREATE INDEX IF NOT EXISTS crm_record_sequence_overrides_record_idx
  ON crm_record_sequence_overrides (crm_record_id);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_conversations_id_record_uq') THEN
    ALTER TABLE crm_conversations ADD CONSTRAINT crm_conversations_id_record_uq
      UNIQUE (id, crm_record_id);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS crm_sequence_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crm_record_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  sequence_id uuid NOT NULL,
  sequence_version_id uuid NOT NULL,
  subcategory_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'active',
  current_step_position integer NOT NULL DEFAULT 1,
  start_step_position integer NOT NULL DEFAULT 1,
  started_by text NOT NULL,
  trigger_message_id uuid NOT NULL,
  last_inbound_at_start timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_sequence_runs_record_fk
    FOREIGN KEY (crm_record_id) REFERENCES crm_records(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_runs_conversation_record_fk
    FOREIGN KEY (conversation_id, crm_record_id)
    REFERENCES crm_conversations(id, crm_record_id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_runs_version_sequence_fk
    FOREIGN KEY (sequence_version_id, sequence_id)
    REFERENCES crm_sequence_versions(id, sequence_id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_runs_subcategory_fk
    FOREIGN KEY (subcategory_id) REFERENCES crm_subcategories(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_runs_trigger_message_fk
    FOREIGN KEY (trigger_message_id) REFERENCES crm_conversation_messages(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_runs_status_chk
    CHECK (status IN ('active', 'interrupted', 'paused', 'completed', 'cancelled')),
  CONSTRAINT crm_sequence_runs_positions_chk
    CHECK (start_step_position > 0 AND current_step_position >= start_step_position),
  CONSTRAINT crm_sequence_runs_started_by_chk
    CHECK (started_by IN ('ai_assignment', 'human_override'))
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_sequence_runs_one_active_uq
  ON crm_sequence_runs (crm_record_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS crm_sequence_runs_record_created_idx
  ON crm_sequence_runs (crm_record_id, created_at);

CREATE TABLE IF NOT EXISTS crm_sequence_step_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sequence_run_id uuid NOT NULL,
  sequence_step_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'scheduled',
  due_at timestamptz NOT NULL,
  draft_id uuid,
  sent_message_id uuid,
  attempt_count integer NOT NULL DEFAULT 0,
  last_error text,
  expected_context_version integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_sequence_step_runs_run_fk
    FOREIGN KEY (sequence_run_id) REFERENCES crm_sequence_runs(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_step_runs_step_fk
    FOREIGN KEY (sequence_step_id) REFERENCES crm_sequence_steps(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_step_runs_sent_message_fk
    FOREIGN KEY (sent_message_id) REFERENCES crm_conversation_messages(id) ON DELETE RESTRICT,
  CONSTRAINT crm_sequence_step_runs_run_step_uq UNIQUE (sequence_run_id, sequence_step_id),
  CONSTRAINT crm_sequence_step_runs_id_run_uq UNIQUE (id, sequence_run_id),
  CONSTRAINT crm_sequence_step_runs_status_chk CHECK (
    status IN ('scheduled', 'drafting', 'awaiting_review', 'sent', 'skipped', 'cancelled', 'failed')
  ),
  CONSTRAINT crm_sequence_step_runs_attempts_chk CHECK (attempt_count >= 0),
  CONSTRAINT crm_sequence_step_runs_context_chk CHECK (expected_context_version >= 0),
  CONSTRAINT crm_sequence_step_runs_sent_message_chk CHECK (status <> 'sent' OR sent_message_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_sequence_step_runs_draft_uq
  ON crm_sequence_step_runs (draft_id) WHERE draft_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS crm_sequence_step_runs_due_idx
  ON crm_sequence_step_runs (status, due_at);

CREATE TABLE IF NOT EXISTS crm_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crm_record_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  reply_for_message_id uuid,
  sequence_step_run_id uuid,
  expected_context_version integer NOT NULL,
  revision integer NOT NULL DEFAULT 1,
  channel text NOT NULL,
  subject text,
  ai_body_text text,
  ai_body_html text,
  edited_body_text text,
  edited_body_html text,
  status text NOT NULL DEFAULT 'generating',
  provider text,
  model text,
  request jsonb,
  response jsonb,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_drafts_record_fk
    FOREIGN KEY (crm_record_id) REFERENCES crm_records(id) ON DELETE RESTRICT,
  CONSTRAINT crm_drafts_conversation_record_fk
    FOREIGN KEY (conversation_id, crm_record_id)
    REFERENCES crm_conversations(id, crm_record_id) ON DELETE RESTRICT,
  CONSTRAINT crm_drafts_reply_message_fk
    FOREIGN KEY (reply_for_message_id) REFERENCES crm_conversation_messages(id) ON DELETE RESTRICT,
  CONSTRAINT crm_drafts_step_run_fk
    FOREIGN KEY (sequence_step_run_id) REFERENCES crm_sequence_step_runs(id) ON DELETE RESTRICT,
  CONSTRAINT crm_drafts_context_chk CHECK (expected_context_version >= 0),
  CONSTRAINT crm_drafts_revision_chk CHECK (revision > 0),
  CONSTRAINT crm_drafts_channel_chk CHECK (channel IN ('email', 'linkedin')),
  CONSTRAINT crm_drafts_linkedin_subject_chk CHECK (channel <> 'linkedin' OR subject IS NULL),
  CONSTRAINT crm_drafts_status_chk CHECK (
    status IN ('generating', 'awaiting_review', 'sending', 'sent', 'discarded', 'stale', 'failed', 'delivery_uncertain')
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_drafts_step_run_uq
  ON crm_drafts (sequence_step_run_id) WHERE sequence_step_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS crm_drafts_record_status_idx ON crm_drafts (crm_record_id, status);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_sequence_step_runs_draft_id_crm_drafts_id_fk') THEN
    ALTER TABLE crm_sequence_step_runs ADD CONSTRAINT crm_sequence_step_runs_draft_id_crm_drafts_id_fk
      FOREIGN KEY (draft_id) REFERENCES crm_drafts(id) ON DELETE RESTRICT;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS crm_send_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL,
  idempotency_key text NOT NULL,
  status text NOT NULL DEFAULT 'prepared',
  actor_type text NOT NULL DEFAULT 'authenticated_operator',
  request_id text NOT NULL,
  provider text NOT NULL,
  account_ref text NOT NULL,
  provider_request_id text,
  provider_message_id text,
  request jsonb,
  response jsonb,
  error text,
  reconciled_at timestamptz,
  reconciliation_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_send_attempts_draft_fk
    FOREIGN KEY (draft_id) REFERENCES crm_drafts(id) ON DELETE RESTRICT,
  CONSTRAINT crm_send_attempts_idempotency_uq UNIQUE (idempotency_key),
  CONSTRAINT crm_send_attempts_idempotency_chk CHECK (length(btrim(idempotency_key)) > 0),
  CONSTRAINT crm_send_attempts_status_chk CHECK (
    status IN ('prepared', 'sending', 'sent', 'failed', 'delivery_uncertain', 'reconciled')
  ),
  CONSTRAINT crm_send_attempts_actor_chk CHECK (actor_type = 'authenticated_operator'),
  CONSTRAINT crm_send_attempts_request_id_chk CHECK (length(btrim(request_id)) > 0),
  CONSTRAINT crm_send_attempts_provider_chk CHECK (length(btrim(provider)) > 0),
  CONSTRAINT crm_send_attempts_account_chk CHECK (length(btrim(account_ref)) > 0),
  CONSTRAINT crm_send_attempts_reconciliation_chk CHECK (
    status <> 'reconciled'
    OR (reconciled_at IS NOT NULL AND length(btrim(reconciliation_note)) > 0)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS crm_send_attempts_one_terminal_uq
  ON crm_send_attempts (draft_id)
  WHERE status IN ('sent', 'delivery_uncertain', 'reconciled');
CREATE INDEX IF NOT EXISTS crm_send_attempts_draft_created_idx
  ON crm_send_attempts (draft_id, created_at);

CREATE TABLE IF NOT EXISTS crm_knowledge_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  kind text NOT NULL,
  tags text[] NOT NULL DEFAULT '{}',
  always_include boolean NOT NULL DEFAULT false,
  active boolean NOT NULL DEFAULT true,
  latest_version integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_knowledge_documents_title_chk CHECK (length(btrim(title)) > 0),
  CONSTRAINT crm_knowledge_documents_kind_chk CHECK (
    kind IN ('company', 'product', 'pricing', 'faq', 'case_study', 'objection', 'scheduling', 'custom')
  ),
  CONSTRAINT crm_knowledge_documents_latest_version_chk CHECK (latest_version > 0)
);
CREATE INDEX IF NOT EXISTS crm_knowledge_documents_active_kind_idx
  ON crm_knowledge_documents (active, kind);

CREATE TABLE IF NOT EXISTS crm_knowledge_document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL,
  version integer NOT NULL,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_knowledge_document_versions_document_fk
    FOREIGN KEY (document_id) REFERENCES crm_knowledge_documents(id) ON DELETE RESTRICT,
  CONSTRAINT crm_knowledge_document_versions_document_version_uq UNIQUE (document_id, version),
  CONSTRAINT crm_knowledge_document_versions_id_document_uq UNIQUE (id, document_id),
  CONSTRAINT crm_knowledge_document_versions_version_chk CHECK (version > 0),
  CONSTRAINT crm_knowledge_document_versions_content_chk CHECK (length(btrim(content)) > 0)
);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_knowledge_documents_latest_version_fk') THEN
    ALTER TABLE crm_knowledge_documents ADD CONSTRAINT crm_knowledge_documents_latest_version_fk
      FOREIGN KEY (id, latest_version)
      REFERENCES crm_knowledge_document_versions(document_id, version)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS crm_draft_knowledge_citations (
  draft_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  excerpt text NOT NULL,
  excerpt_hash text NOT NULL,
  rank numeric NOT NULL,
  CONSTRAINT crm_draft_knowledge_citations_pk
    PRIMARY KEY (draft_id, document_version_id, excerpt_hash),
  CONSTRAINT crm_draft_knowledge_citations_draft_fk
    FOREIGN KEY (draft_id) REFERENCES crm_drafts(id) ON DELETE RESTRICT,
  CONSTRAINT crm_draft_knowledge_citations_version_fk
    FOREIGN KEY (document_version_id) REFERENCES crm_knowledge_document_versions(id) ON DELETE RESTRICT,
  CONSTRAINT crm_draft_knowledge_citations_excerpt_chk CHECK (length(btrim(excerpt)) > 0),
  CONSTRAINT crm_draft_knowledge_citations_hash_chk CHECK (length(btrim(excerpt_hash)) > 0),
  CONSTRAINT crm_draft_knowledge_citations_rank_chk CHECK (rank >= 0)
);

CREATE TABLE IF NOT EXISTS crm_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  idempotency_key text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}',
  priority integer NOT NULL DEFAULT 0,
  attempts integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  run_after timestamptz NOT NULL DEFAULT now(),
  locked_at timestamptz,
  locked_by text,
  started_at timestamptz,
  completed_at timestamptz,
  failed_at timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT crm_jobs_idempotency_uq UNIQUE (idempotency_key),
  CONSTRAINT crm_jobs_entity_uq UNIQUE (kind, entity_type, entity_id),
  CONSTRAINT crm_jobs_kind_chk
    CHECK (kind IN ('classification', 'initial_draft', 'due_followup_draft')),
  CONSTRAINT crm_jobs_status_chk CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  CONSTRAINT crm_jobs_entity_type_chk
    CHECK (entity_type IN ('message', 'classification', 'sequence_step_run')),
  CONSTRAINT crm_jobs_kind_entity_chk CHECK (
    (kind = 'classification' AND entity_type = 'message')
    OR (kind = 'initial_draft' AND entity_type = 'classification')
    OR (kind = 'due_followup_draft' AND entity_type = 'sequence_step_run')
  ),
  CONSTRAINT crm_jobs_idempotency_chk CHECK (length(btrim(idempotency_key)) > 0),
  CONSTRAINT crm_jobs_attempts_chk
    CHECK (attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts),
  CONSTRAINT crm_jobs_lock_chk CHECK (
    (status = 'running' AND locked_at IS NOT NULL AND locked_by IS NOT NULL AND started_at IS NOT NULL)
    OR (status <> 'running' AND locked_at IS NULL AND locked_by IS NULL)
  ),
  CONSTRAINT crm_jobs_completion_chk
    CHECK ((status IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)),
  CONSTRAINT crm_jobs_failure_chk CHECK (
    ((status = 'failed') = (failed_at IS NOT NULL))
    AND (status <> 'failed' OR length(btrim(last_error)) > 0)
  )
);
CREATE INDEX IF NOT EXISTS crm_jobs_claim_idx ON crm_jobs (status, run_after, priority);
CREATE INDEX IF NOT EXISTS crm_jobs_stale_claim_idx ON crm_jobs (status, locked_at);

CREATE OR REPLACE FUNCTION crm_sequences_validate_version_pointers()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_draft uuid; current_published uuid; expected_published uuid;
BEGIN
  SELECT draft_version_id, latest_published_version_id
    INTO current_draft, current_published
    FROM crm_sequences WHERE id = NEW.id;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_versions
     WHERE id = current_draft AND sequence_id = NEW.id AND status = 'draft'
  ) THEN
    RAISE EXCEPTION 'draft_version_id must identify this sequence draft version'
      USING ERRCODE = 'check_violation';
  END IF;
  IF current_published IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_sequence_versions
     WHERE id = current_published AND sequence_id = NEW.id AND status = 'published'
  ) THEN
    RAISE EXCEPTION 'latest_published_version_id must identify this sequence published version'
      USING ERRCODE = 'check_violation';
  END IF;
  SELECT id INTO expected_published FROM crm_sequence_versions
   WHERE sequence_id = NEW.id AND status = 'published'
   ORDER BY version DESC LIMIT 1;
  IF current_published IS DISTINCT FROM expected_published THEN
    RAISE EXCEPTION 'latest_published_version_id must identify the newest published version'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequences_validate_version_pointers_trg ON crm_sequences;
CREATE CONSTRAINT TRIGGER crm_sequences_validate_version_pointers_trg
  AFTER INSERT OR UPDATE ON crm_sequences
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION crm_sequences_validate_version_pointers();

CREATE OR REPLACE FUNCTION crm_sequence_versions_validate_owner_pointers()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_id uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.sequence_id ELSE NEW.sequence_id END;
        current_draft uuid; current_published uuid; expected_published uuid;
BEGIN
  SELECT draft_version_id, latest_published_version_id
    INTO current_draft, current_published FROM crm_sequences WHERE id = owner_id;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_versions
     WHERE id = current_draft AND sequence_id = owner_id AND status = 'draft'
  ) THEN
    RAISE EXCEPTION 'sequence must point to its mutable draft version'
      USING ERRCODE = 'check_violation';
  END IF;
  SELECT id INTO expected_published FROM crm_sequence_versions
   WHERE sequence_id = owner_id AND status = 'published'
   ORDER BY version DESC LIMIT 1;
  IF current_published IS DISTINCT FROM expected_published THEN
    RAISE EXCEPTION 'sequence must point to its newest published version'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequence_versions_validate_owner_pointers_trg ON crm_sequence_versions;
CREATE CONSTRAINT TRIGGER crm_sequence_versions_validate_owner_pointers_trg
  AFTER INSERT OR UPDATE OR DELETE ON crm_sequence_versions
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION crm_sequence_versions_validate_owner_pointers();

CREATE OR REPLACE FUNCTION crm_sequence_versions_protect_published()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND OLD.status = 'published' THEN
    RAISE EXCEPTION 'published sequence versions are immutable' USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status = 'published' THEN
    RAISE EXCEPTION 'published sequence versions are immutable' USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.status = 'published' AND OLD.status = 'draft' AND NOT EXISTS (
    SELECT 1 FROM crm_sequence_steps
     WHERE sequence_version_id = NEW.id AND position = 1 AND step_type = 'reply' AND delay_minutes = 0
  ) THEN
    RAISE EXCEPTION 'a sequence cannot be published without an immediate reply step'
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND (
    OLD.id IS DISTINCT FROM NEW.id OR OLD.sequence_id IS DISTINCT FROM NEW.sequence_id
    OR OLD.version IS DISTINCT FROM NEW.version
  ) THEN
    RAISE EXCEPTION 'sequence version identity is immutable' USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequence_versions_protect_published_trg ON crm_sequence_versions;
CREATE TRIGGER crm_sequence_versions_protect_published_trg
  BEFORE UPDATE OR DELETE ON crm_sequence_versions
  FOR EACH ROW EXECUTE FUNCTION crm_sequence_versions_protect_published();

CREATE OR REPLACE FUNCTION crm_sequence_steps_require_draft()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_version_id uuid := COALESCE(NEW.sequence_version_id, OLD.sequence_version_id);
BEGIN
  IF NOT EXISTS (SELECT 1 FROM crm_sequence_versions WHERE id = target_version_id AND status = 'draft') THEN
    RAISE EXCEPTION 'sequence steps can be changed only on a draft version'
      USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequence_steps_require_draft_trg ON crm_sequence_steps;
CREATE TRIGGER crm_sequence_steps_require_draft_trg
  BEFORE INSERT OR UPDATE OR DELETE ON crm_sequence_steps
  FOR EACH ROW EXECUTE FUNCTION crm_sequence_steps_require_draft();

CREATE OR REPLACE FUNCTION crm_sequence_runs_validate_scope()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE record_pipeline uuid; conversation_channel text;
BEGIN
  SELECT pipeline_id INTO record_pipeline FROM crm_records WHERE id = NEW.crm_record_id;
  SELECT channel INTO conversation_channel FROM crm_conversations
   WHERE id = NEW.conversation_id AND crm_record_id = NEW.crm_record_id;
  IF conversation_channel IS NULL THEN
    RAISE EXCEPTION 'sequence run conversation must belong to its CRM record'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_versions
     WHERE id = NEW.sequence_version_id AND sequence_id = NEW.sequence_id AND status = 'published'
  ) THEN
    RAISE EXCEPTION 'sequence runs must pin a published version'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_subcategories WHERE id = NEW.subcategory_id AND pipeline_id = record_pipeline
  ) THEN
    RAISE EXCEPTION 'sequence run subcategory must belong to its record pipeline'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_conversation_messages
     WHERE id = NEW.trigger_message_id AND conversation_id = NEW.conversation_id AND direction = 'inbound'
  ) THEN
    RAISE EXCEPTION 'sequence run trigger must be an inbound message in its conversation'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_steps
     WHERE sequence_version_id = NEW.sequence_version_id AND position = NEW.start_step_position
  ) THEN
    RAISE EXCEPTION 'sequence run start step must exist in the pinned version'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_steps
     WHERE sequence_version_id = NEW.sequence_version_id AND position = NEW.current_step_position
  ) THEN
    RAISE EXCEPTION 'sequence run current step must exist in the pinned version'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequence_runs_validate_scope_trg ON crm_sequence_runs;
CREATE TRIGGER crm_sequence_runs_validate_scope_trg
  BEFORE INSERT OR UPDATE ON crm_sequence_runs
  FOR EACH ROW EXECUTE FUNCTION crm_sequence_runs_validate_scope();

CREATE OR REPLACE FUNCTION crm_sequence_step_runs_validate_scope()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pinned_version uuid; run_conversation uuid;
BEGIN
  SELECT sequence_version_id, conversation_id INTO pinned_version, run_conversation
    FROM crm_sequence_runs WHERE id = NEW.sequence_run_id;
  IF NOT EXISTS (
    SELECT 1 FROM crm_sequence_steps WHERE id = NEW.sequence_step_id AND sequence_version_id = pinned_version
  ) THEN
    RAISE EXCEPTION 'step run step must belong to the run pinned version'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.sent_message_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_conversation_messages
     WHERE id = NEW.sent_message_id AND conversation_id = run_conversation AND direction = 'outbound'
  ) THEN
    RAISE EXCEPTION 'sent message must be outbound in the sequence run conversation'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_sequence_step_runs_validate_scope_trg ON crm_sequence_step_runs;
CREATE TRIGGER crm_sequence_step_runs_validate_scope_trg
  BEFORE INSERT OR UPDATE ON crm_sequence_step_runs
  FOR EACH ROW EXECUTE FUNCTION crm_sequence_step_runs_validate_scope();

CREATE OR REPLACE FUNCTION crm_drafts_validate_scope()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE conversation_channel text;
BEGIN
  SELECT channel INTO conversation_channel FROM crm_conversations
   WHERE id = NEW.conversation_id AND crm_record_id = NEW.crm_record_id;
  IF conversation_channel IS NULL OR conversation_channel <> NEW.channel THEN
    RAISE EXCEPTION 'draft channel and record must match its conversation'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.reply_for_message_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_conversation_messages
     WHERE id = NEW.reply_for_message_id AND conversation_id = NEW.conversation_id AND direction = 'inbound'
  ) THEN
    RAISE EXCEPTION 'reply draft target must be inbound in its conversation'
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.sequence_step_run_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM crm_sequence_step_runs step_run
      JOIN crm_sequence_runs run ON run.id = step_run.sequence_run_id
     WHERE step_run.id = NEW.sequence_step_run_id
       AND run.crm_record_id = NEW.crm_record_id
       AND run.conversation_id = NEW.conversation_id
  ) THEN
    RAISE EXCEPTION 'draft step run must belong to its record and conversation'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_drafts_validate_scope_trg ON crm_drafts;
CREATE TRIGGER crm_drafts_validate_scope_trg
  BEFORE INSERT OR UPDATE ON crm_drafts
  FOR EACH ROW EXECUTE FUNCTION crm_drafts_validate_scope();

CREATE OR REPLACE FUNCTION crm_send_attempts_validate_account()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM crm_drafts draft
      JOIN crm_conversations conversation ON conversation.id = draft.conversation_id
     WHERE draft.id = NEW.draft_id AND conversation.account_ref = NEW.account_ref
  ) THEN
    RAISE EXCEPTION 'send attempt account must match the draft conversation account'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_send_attempts_validate_account_trg ON crm_send_attempts;
CREATE TRIGGER crm_send_attempts_validate_account_trg
  BEFORE INSERT OR UPDATE ON crm_send_attempts
  FOR EACH ROW EXECUTE FUNCTION crm_send_attempts_validate_account();

CREATE OR REPLACE FUNCTION crm_send_attempts_protect_terminal()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('sent', 'reconciled') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'a terminal send attempt cannot change status'
      USING ERRCODE = 'check_violation';
  END IF;
  IF OLD.status = 'delivery_uncertain'
     AND NEW.status NOT IN ('delivery_uncertain', 'reconciled') THEN
    RAISE EXCEPTION 'delivery-uncertain attempts require reconciliation'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_send_attempts_protect_terminal_trg ON crm_send_attempts;
CREATE TRIGGER crm_send_attempts_protect_terminal_trg
  BEFORE UPDATE ON crm_send_attempts
  FOR EACH ROW EXECUTE FUNCTION crm_send_attempts_protect_terminal();

CREATE OR REPLACE FUNCTION crm_knowledge_versions_append_only()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Knowledge document versions are append-only' USING ERRCODE = 'restrict_violation';
END;
$$;
DROP TRIGGER IF EXISTS crm_knowledge_versions_append_only_trg ON crm_knowledge_document_versions;
CREATE TRIGGER crm_knowledge_versions_append_only_trg
  BEFORE UPDATE OR DELETE ON crm_knowledge_document_versions
  FOR EACH ROW EXECUTE FUNCTION crm_knowledge_versions_append_only();

CREATE OR REPLACE FUNCTION crm_knowledge_versions_validate_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_version integer;
BEGIN
  SELECT COALESCE(max(version), 0) + 1 INTO expected_version
    FROM crm_knowledge_document_versions WHERE document_id = NEW.document_id;
  IF NEW.version <> expected_version THEN
    RAISE EXCEPTION 'Knowledge versions must be consecutive; expected %', expected_version
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_knowledge_versions_validate_insert_trg ON crm_knowledge_document_versions;
CREATE TRIGGER crm_knowledge_versions_validate_insert_trg
  BEFORE INSERT ON crm_knowledge_document_versions
  FOR EACH ROW EXECUTE FUNCTION crm_knowledge_versions_validate_insert();

CREATE OR REPLACE FUNCTION crm_knowledge_documents_validate_latest()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE maximum_version integer;
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.latest_version < OLD.latest_version THEN
    RAISE EXCEPTION 'Knowledge latest version cannot move backwards' USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.latest_version IS DISTINCT FROM OLD.latest_version THEN
    SELECT max(version) INTO maximum_version
      FROM crm_knowledge_document_versions WHERE document_id = NEW.id;
    IF maximum_version IS NULL OR NEW.latest_version <> maximum_version THEN
      RAISE EXCEPTION 'latest_version must point at the newest Knowledge version'
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_knowledge_documents_validate_latest_trg ON crm_knowledge_documents;
CREATE TRIGGER crm_knowledge_documents_validate_latest_trg
  BEFORE INSERT OR UPDATE ON crm_knowledge_documents
  FOR EACH ROW EXECUTE FUNCTION crm_knowledge_documents_validate_latest();

CREATE OR REPLACE FUNCTION crm_knowledge_versions_validate_owner_latest()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_id uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.document_id ELSE NEW.document_id END;
        declared_latest integer; maximum_version integer;
BEGIN
  SELECT latest_version INTO declared_latest FROM crm_knowledge_documents WHERE id = owner_id;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;
  SELECT max(version) INTO maximum_version
    FROM crm_knowledge_document_versions WHERE document_id = owner_id;
  IF declared_latest IS DISTINCT FROM maximum_version THEN
    RAISE EXCEPTION 'Knowledge latest_version must identify its newest version'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS crm_knowledge_versions_validate_owner_latest_trg ON crm_knowledge_document_versions;
CREATE CONSTRAINT TRIGGER crm_knowledge_versions_validate_owner_latest_trg
  AFTER INSERT OR UPDATE OR DELETE ON crm_knowledge_document_versions
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION crm_knowledge_versions_validate_owner_latest();

CREATE OR REPLACE FUNCTION crm_jobs_validate_entity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.entity_type = 'message'
     AND NOT EXISTS (SELECT 1 FROM crm_conversation_messages WHERE id = NEW.entity_id) THEN
    RAISE EXCEPTION 'classification job message does not exist' USING ERRCODE = 'foreign_key_violation';
  ELSIF NEW.entity_type = 'classification'
     AND NOT EXISTS (SELECT 1 FROM crm_classifications WHERE id = NEW.entity_id) THEN
    RAISE EXCEPTION 'initial draft job classification does not exist' USING ERRCODE = 'foreign_key_violation';
  ELSIF NEW.entity_type = 'sequence_step_run'
     AND NOT EXISTS (SELECT 1 FROM crm_sequence_step_runs WHERE id = NEW.entity_id) THEN
    RAISE EXCEPTION 'follow-up draft job step run does not exist' USING ERRCODE = 'foreign_key_violation';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS crm_jobs_validate_entity_trg ON crm_jobs;
CREATE TRIGGER crm_jobs_validate_entity_trg
  BEFORE INSERT OR UPDATE OF entity_type, entity_id ON crm_jobs
  FOR EACH ROW EXECUTE FUNCTION crm_jobs_validate_entity();

-- Safe starter templates. They remain mutable drafts and are never assigned,
-- published, scheduled, or sent by this migration.
INSERT INTO crm_sequences (id, name, description, draft_version_id)
VALUES
  ('10000000-0000-0000-0000-000000000101', 'Example inbound reply', 'Starter template for Email or LinkedIn; review and publish before assigning.', '10000000-0000-0000-0000-000000000111')
ON CONFLICT (id) DO NOTHING;

INSERT INTO crm_sequence_versions (id, sequence_id, version, status)
VALUES
  ('10000000-0000-0000-0000-000000000111', '10000000-0000-0000-0000-000000000101', 1, 'draft')
ON CONFLICT (id) DO NOTHING;

INSERT INTO crm_sequence_steps
  (id, sequence_version_id, position, step_type, name, delay_minutes, subject_template, body_template, ai_instructions, knowledge_tags)
VALUES
  ('10000000-0000-0000-0000-000000000121', '10000000-0000-0000-0000-000000000111', 1, 'reply', 'Immediate Reply', 0, 'Re: {{subject}}', 'Hi {{first_name}},', 'Respond helpfully to the latest request and propose a clear next step.', ARRAY[]::text[]),
  ('10000000-0000-0000-0000-000000000122', '10000000-0000-0000-0000-000000000111', 2, 'follow_up', 'Follow-up 1', 1440, 'Re: {{subject}}', 'Hi {{first_name}},', 'Follow up briefly and respectfully. Do not imply that an earlier reply was received.', ARRAY[]::text[])
ON CONFLICT (id) DO NOTHING;
`;

const EXPECTED_TABLES = [
  "crm_draft_knowledge_citations",
  "crm_drafts",
  "crm_jobs",
  "crm_knowledge_document_versions",
  "crm_knowledge_documents",
  "crm_record_sequence_overrides",
  "crm_send_attempts",
  "crm_sequence_runs",
  "crm_sequence_step_runs",
  "crm_sequence_steps",
  "crm_sequence_versions",
  "crm_sequences",
  "crm_subcategory_sequence_assignments",
] as const;

const EXPECTED_TRIGGERS = [
  "crm_drafts_validate_scope_trg",
  "crm_jobs_validate_entity_trg",
  "crm_knowledge_documents_validate_latest_trg",
  "crm_knowledge_versions_append_only_trg",
  "crm_knowledge_versions_validate_insert_trg",
  "crm_knowledge_versions_validate_owner_latest_trg",
  "crm_send_attempts_validate_account_trg",
  "crm_send_attempts_protect_terminal_trg",
  "crm_sequence_runs_validate_scope_trg",
  "crm_sequence_step_runs_validate_scope_trg",
  "crm_sequence_steps_require_draft_trg",
  "crm_sequence_versions_protect_published_trg",
  "crm_sequence_versions_validate_owner_pointers_trg",
  "crm_sequences_validate_version_pointers_trg",
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
        `SELECT table_name FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = ANY($1::text[])
          ORDER BY table_name`,
        [EXPECTED_TABLES],
      );
      const actual = rows.map((row) => row.table_name);
      if (actual.length !== EXPECTED_TABLES.length || actual.some((name, index) => name !== EXPECTED_TABLES[index])) {
        throw new Error(`CRM workflow table verification failed: ${JSON.stringify(actual)}`);
      }
      const { rows: triggerRows } = await client.query<{ n: string }>(
        `SELECT count(*)::text AS n FROM pg_trigger
          WHERE tgname = ANY($1::text[]) AND NOT tgisinternal`,
        [EXPECTED_TRIGGERS],
      );
      if (triggerRows[0]?.n !== String(EXPECTED_TRIGGERS.length)) {
        throw new Error("CRM workflow trigger verification failed");
      }
      await client.query("COMMIT");
      console.log(`CRM workflow ready: tables=${actual.length}`);
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
