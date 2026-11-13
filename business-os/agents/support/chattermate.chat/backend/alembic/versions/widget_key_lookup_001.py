"""Look widget API keys up by a SHA-256 of the key

Checking a key used to bcrypt it against every active widget app, about
100ms each, on the request's event loop, so each wrong key stalled the API
in proportion to the number of apps. widget_apps.api_key_lookup holds a
SHA-256 of the key (safe for a 256-bit random secret) so a key is one
indexed lookup. Keys issued earlier stay NULL until they are next used.

Revision ID: widget_key_lookup_001
Revises: session_conversation_key_001
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'widget_key_lookup_001'
down_revision: Union[str, None] = 'session_conversation_key_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_widget_apps_api_key_lookup'


def upgrade() -> None:
    op.add_column('widget_apps', sa.Column('api_key_lookup', sa.String(64), nullable=True), if_not_exists=True)
    op.create_index(INDEX_NAME, 'widget_apps', ['api_key_lookup'], unique=True, if_not_exists=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='widget_apps', if_exists=True)
    op.drop_column('widget_apps', 'api_key_lookup', if_exists=True)
