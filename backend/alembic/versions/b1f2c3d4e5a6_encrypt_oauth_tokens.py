"""encrypt oauth tokens at rest

Widens user_sessions.access_token / refresh_token to hold Fernet ciphertext and
purges any existing rows (their tokens were stored as plaintext and cannot be
decrypted under the new EncryptedString type — affected users simply re-login).

Revision ID: b1f2c3d4e5a6
Revises: 08637bcf6cb7
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f2c3d4e5a6'
down_revision: Union[str, Sequence[str], None] = '08637bcf6cb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Old plaintext tokens are undecryptable under EncryptedString; drop them so
    # nothing tries to decrypt plaintext on next read. Sessions are re-created on
    # the next Spotify login.
    op.execute("DELETE FROM user_sessions")
    op.alter_column(
        'user_sessions', 'access_token',
        existing_type=sa.String(length=2048),
        type_=sa.String(length=4096),
        existing_nullable=False,
    )
    op.alter_column(
        'user_sessions', 'refresh_token',
        existing_type=sa.String(length=2048),
        type_=sa.String(length=4096),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'user_sessions', 'refresh_token',
        existing_type=sa.String(length=4096),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )
    op.alter_column(
        'user_sessions', 'access_token',
        existing_type=sa.String(length=4096),
        type_=sa.String(length=2048),
        existing_nullable=False,
    )
