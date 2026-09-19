"""voice clip audio stored in db, not disk

Revision ID: c1a2f4b9d3e7
Revises: a563f76c6c7e
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2f4b9d3e7'
down_revision: Union[str, Sequence[str], None] = 'a563f76c6c7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('voice_clips', sa.Column('audio_data', sa.LargeBinary(), nullable=True))
    op.execute("UPDATE voice_clips SET audio_data = E'\\\\x'")
    op.alter_column('voice_clips', 'audio_data', nullable=False)
    op.drop_column('voice_clips', 'file_path')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('voice_clips', sa.Column('file_path', sa.String(length=500), nullable=True))
    op.execute("UPDATE voice_clips SET file_path = ''")
    op.alter_column('voice_clips', 'file_path', nullable=False)
    op.drop_column('voice_clips', 'audio_data')

