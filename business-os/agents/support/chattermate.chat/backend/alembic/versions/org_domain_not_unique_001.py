"""organizations.domain is no longer unique

Revision ID: org_domain_not_unique_001
Revises: widget_allowed_domains_001
Create Date: 2026-10-22

The widget is framed from our own origin, so an org's website no longer has to
be in CORS to work, and two orgs may run on the same site. The column stays
required: the website seeds the agent's knowledge and the setup emails.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'org_domain_not_unique_001'
down_revision: Union[str, None] = 'widget_allowed_domains_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every unique constraint, then every other unique index, on just the domain
# column, whatever it's called: a database built by hand may differ from ours
DROP_UNIQUE_DOMAIN = """
    DO $$
    DECLARE item record;
    BEGIN
        FOR item IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
            WHERE con.conrelid = 'organizations'::regclass AND con.contype = 'u'
              AND cardinality(con.conkey) = 1 AND att.attname = 'domain'
        LOOP
            EXECUTE format('ALTER TABLE organizations DROP CONSTRAINT %I', item.conname);
        END LOOP;
        FOR item IN
            SELECT ns.nspname, idx.relname
            FROM pg_index i
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace ns ON ns.oid = idx.relnamespace
            JOIN pg_attribute att ON att.attrelid = i.indrelid AND att.attnum = i.indkey[0]
            WHERE i.indrelid = 'organizations'::regclass AND i.indisunique
              AND i.indnatts = 1 AND att.attname = 'domain'
        LOOP
            EXECUTE format('DROP INDEX %I.%I', item.nspname, item.relname);
        END LOOP;
    END $$;
"""


def upgrade() -> None:
    op.execute(DROP_UNIQUE_DOMAIN)


def downgrade() -> None:
    shared = op.get_bind().execute(sa.text(
        "SELECT domain FROM organizations GROUP BY domain HAVING count(*) > 1 LIMIT 5"
    )).scalars().all()
    if shared:
        raise RuntimeError(
            "Can't make organization websites unique again: more than one "
            f"organization uses {', '.join(shared)}")
    op.execute("ALTER TABLE organizations ADD CONSTRAINT organizations_domain_key UNIQUE (domain)")
