"""Scope widget conversations and customers to the token that created them

A widget token the visitor obtained without proving who they are may name an
existing customer. session_to_agents.conversation_key records which token scope
created a session, so such a token only resumes its own conversations; existing
rows stay NULL, the scope of tokens the embedding app vouched for.
customers.conversation_key records which widget scope created a customer, so a
token may only edit or merge a customer it created itself.

Every scope check filters session_to_agents by customer_id, which had no index;
the index is built CONCURRENTLY so the table keeps taking writes while the
backend starts. That can't run in a transaction, hence the autocommit block. A
build that fails part-way leaves an INVALID index that IF NOT EXISTS would then
skip: if that happens, DROP INDEX ix_session_to_agents_customer_id and restart.

Revision ID: session_conversation_key_001
Revises: auth_sessions_001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Keep revision ids under 32 characters: alembic_version.version_num is
# varchar(32).
revision: str = 'session_conversation_key_001'
down_revision: Union[str, None] = 'auth_sessions_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_session_to_agents_customer_id'


def upgrade() -> None:
    op.add_column('session_to_agents', sa.Column('conversation_key', sa.String(64), nullable=True),
                  if_not_exists=True)
    op.add_column('customers', sa.Column('conversation_key', sa.String(64), nullable=True),
                  if_not_exists=True)
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME, 'session_to_agents', ['customer_id'],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX_NAME, table_name='session_to_agents',
                      postgresql_concurrently=True, if_exists=True)
    op.drop_column('customers', 'conversation_key', if_exists=True)
    op.drop_column('session_to_agents', 'conversation_key', if_exists=True)
