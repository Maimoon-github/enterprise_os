\set ON_ERROR_STOP on

-- Simulate a prior interrupted run: one unresolved source has already been
-- linked, while the same source in another campaign remains unlinked.
INSERT INTO people (id, full_name, raw, source)
VALUES ('20000000-0000-0000-0000-000000000001', 'Provisional Person', '{}', 'fixture:partial-backfill');

UPDATE "Lead"
SET "personId" = '20000000-0000-0000-0000-000000000001',
    "sourceLinkedinIdentifier" = 'ACwAAEncoded,NAME,abc',
    "sourceLinkedinApi" = NULL
WHERE id = 'lead-provisional-a';
