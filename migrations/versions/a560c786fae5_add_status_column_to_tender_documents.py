"""add status column to tender_documents

Revision ID: a560c786fae5
Revises: f7f0014dfddc
Create Date: 2025-03-26 12:14:23.827897

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a560c786fae5'
down_revision: Union[str, None] = 'f7f0014dfddc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tender_documents', sa.Column('status', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tender_documents', 'status')
    
