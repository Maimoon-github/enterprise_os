"""Track channel delivery receipts on chat_history

WhatsApp reports sent / delivered / read / failed for every message we send,
keyed by its platform message id (wamid). Storing that id on the row is what
lets a receipt find its message; channel_status holds the latest receipt.

channel_status is deliberately separate from attributes.delivery_status: the
inbox reads any delivery_status as "not delivered", so a 'read' written there
would show as a failure.

Revision ID: chat_channel_status_001
Revises: idx_kq_org_status_001
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Keep revision ids under 32 characters: alembic_version.version_num is
# varchar(32).
revision: str = 'chat_channel_status_001'
down_revision: Union[str, None] = 'idx_kq_org_status_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_chat_history_org_external_message'


def upgrade() -> None:
    # if_not_exists throughout: the columns commit before the index builds
    # (CONCURRENTLY can't share their transaction), so a start that dies
    # mid-build must be able to run this again.
    op.add_column('chat_history', sa.Column('external_message_id', sa.String(), nullable=True),
                  if_not_exists=True)
    op.add_column('chat_history', sa.Column('channel_status', sa.String(16), nullable=True),
                  if_not_exists=True)
    op.add_column('chat_history', sa.Column('channel_status_at', sa.TIMESTAMP(timezone=True),
                                            nullable=True),
                  if_not_exists=True)
    # Partial: only channel messages carry an id, so widget rows stay out of it.
    # Built CONCURRENTLY so a large chat_history keeps taking writes while it
    # builds — migrations run on backend start. That can't run in a
    # transaction, hence the autocommit block. A build that fails part-way
    # leaves an INVALID index that IF NOT EXISTS would then skip: if that
    # happens, DROP INDEX ix_chat_history_org_external_message and restart.
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME, 'chat_history', ['organization_id', 'external_message_id'],
            unique=False,
            postgresql_where=sa.text('external_message_id IS NOT NULL'),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX_NAME, table_name='chat_history',
                      postgresql_concurrently=True, if_exists=True)
    op.drop_column('chat_history', 'channel_status_at', if_exists=True)
    op.drop_column('chat_history', 'channel_status', if_exists=True)
    op.drop_column('chat_history', 'external_message_id', if_exists=True)
