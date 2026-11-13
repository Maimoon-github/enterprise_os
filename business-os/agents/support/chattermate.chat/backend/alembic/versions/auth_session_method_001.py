"""auth_sessions.auth_method and identity_id: how a session was opened

Revision ID: auth_session_method_001
Revises: user_identities_001
Create Date: 2026-10-22

NULL on existing sessions, which predate the record.

Every sign-in writes auth_sessions, so the identity_id index is built
CONCURRENTLY (outside the transaction, hence the autocommit block) and only
over SSO sessions, the rows unlinking looks up. A build that fails part-way
leaves an INVALID index that IF NOT EXISTS would then skip: if that happens,
DROP INDEX ix_auth_sessions_identity_id and restart.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'auth_session_method_001'
down_revision: Union[str, None] = 'user_identities_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = 'ix_auth_sessions_identity_id'


def upgrade() -> None:
    op.add_column('auth_sessions', sa.Column('auth_method', sa.String(), nullable=True))
    op.add_column('auth_sessions', sa.Column('identity_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_auth_sessions_identity_id', 'auth_sessions', 'user_identities',
        ['identity_id'], ['id'], ondelete='SET NULL',
    )
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME, 'auth_sessions', ['identity_id'],
            postgresql_where=sa.text('identity_id IS NOT NULL'),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(INDEX_NAME, table_name='auth_sessions',
                      postgresql_concurrently=True, if_exists=True)
    op.drop_constraint('fk_auth_sessions_identity_id', 'auth_sessions', type_='foreignkey')
    op.drop_column('auth_sessions', 'identity_id')
    op.drop_column('auth_sessions', 'auth_method')
