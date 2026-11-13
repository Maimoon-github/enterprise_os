"""user_identities table, linking SSO accounts to dashboard users

Revision ID: user_identities_001
Revises: org_domain_not_unique_001
Create Date: 2026-10-22

Empty on deploy: each SSO account is linked on its first sign-in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'user_identities_001'
down_revision: Union[str, None] = 'org_domain_not_unique_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_identities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('issuer', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'issuer', 'subject',
                            name='uq_user_identities_provider_issuer_subject'),
        # One account per provider per user; also serves lookups by user.
        sa.UniqueConstraint('user_id', 'provider',
                            name='uq_user_identities_user_provider'),
    )


def downgrade() -> None:
    op.drop_table('user_identities')
