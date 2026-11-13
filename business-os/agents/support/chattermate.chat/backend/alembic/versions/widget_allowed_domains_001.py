"""widgets.allowed_domains, the sites a widget may be embedded on

Revision ID: widget_allowed_domains_001
Revises: widget_key_lookup_001
Create Date: 2026-10-14

NULL for every existing widget, which means embeddable anywhere.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'widget_allowed_domains_001'
down_revision: Union[str, None] = 'widget_key_lookup_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('widgets', sa.Column('allowed_domains', sa.JSON(), nullable=True), if_not_exists=True)


def downgrade() -> None:
    op.drop_column('widgets', 'allowed_domains', if_exists=True)
