"""Let an agent offer reply buttons on messaging channels

Off by default: an agent shows the AI's choices as tappable buttons on
WhatsApp, Messenger, Instagram and Telegram only once someone turns it on.

Revision ID: agent_quick_replies_001
Revises: chat_channel_status_001
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Keep revision ids under 32 characters: alembic_version.version_num is
# varchar(32).
revision: str = 'agent_quick_replies_001'
down_revision: Union[str, None] = 'chat_channel_status_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('channel_quick_replies', sa.Boolean(), nullable=False,
                                      server_default=sa.false()), if_not_exists=True)


def downgrade() -> None:
    op.drop_column('agents', 'channel_quick_replies', if_exists=True)
