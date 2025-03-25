"""UserTender modified + situation added

Revision ID: 4b2af185d819
Revises: e0cb195be6a4
Create Date: 2025-03-21 21:36:36.585479

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '4b2af185d819'
down_revision: Union[str, None] = 'e0cb195be6a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns
    op.add_column('user_tenders', sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))
    op.add_column('user_tenders', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))
    op.add_column('user_tenders', sa.Column('situation', sa.String(length=50), nullable=True))
    
    # Using raw SQL to handle SQL Server-specific operations
    # First drop the existing unique constraint
    op.execute("IF EXISTS (SELECT * FROM sys.key_constraints WHERE name = 'uq_user_tender') ALTER TABLE user_tenders DROP CONSTRAINT uq_user_tender")
    
    # Create index on tender_uri
    op.create_index(op.f('ix_user_tenders_tender_uri'), 'user_tenders', ['tender_uri'], unique=False)
    
    # Drop index on tender_id
    op.execute("IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_user_tenders_tender_id') DROP INDEX ix_user_tenders_tender_id ON user_tenders")
    
    # Find and drop default constraint for saved_at
    op.execute("""
    DECLARE @DefaultConstraintName nvarchar(200)
    SELECT @DefaultConstraintName = name
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('user_tenders')
    AND col_name(parent_object_id, parent_column_id) = 'saved_at'
    
    IF @DefaultConstraintName IS NOT NULL
        EXEC('ALTER TABLE user_tenders DROP CONSTRAINT ' + @DefaultConstraintName)
    """)
    
    # Find and drop default constraint for tender_id if it exists
    op.execute("""
    DECLARE @DefaultConstraintName nvarchar(200)
    SELECT @DefaultConstraintName = name
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('user_tenders')
    AND col_name(parent_object_id, parent_column_id) = 'tender_id'
    
    IF @DefaultConstraintName IS NOT NULL
        EXEC('ALTER TABLE user_tenders DROP CONSTRAINT ' + @DefaultConstraintName)
    """)
    
    # Now drop the columns
    op.drop_column('user_tenders', 'tender_id')
    op.drop_column('user_tenders', 'saved_at')
    
    # Create new unique constraint
    op.create_unique_constraint('uq_user_tender', 'user_tenders', ['user_id', 'tender_uri'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new unique constraint
    op.execute("IF EXISTS (SELECT * FROM sys.key_constraints WHERE name = 'uq_user_tender') ALTER TABLE user_tenders DROP CONSTRAINT uq_user_tender")
    
    # Add back the original columns
    op.add_column('user_tenders', sa.Column('saved_at', sa.DATETIME(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))
    op.add_column('user_tenders', sa.Column('tender_id', sa.VARCHAR(length=255), nullable=True))
    
    # Update tender_id from tender_uri for existing records
    op.execute("""
    UPDATE user_tenders 
    SET tender_id = RIGHT(tender_uri, CHARINDEX('/', REVERSE(tender_uri)) - 1)
    """)
    
    # Make tender_id non-nullable
    op.alter_column('user_tenders', 'tender_id', nullable=False)
    
    # Drop index on tender_uri
    op.drop_index(op.f('ix_user_tenders_tender_uri'), table_name='user_tenders')
    
    # Create index on tender_id
    op.create_index('ix_user_tenders_tender_id', 'user_tenders', ['tender_id'], unique=False)
    
    # Create unique constraint
    op.create_unique_constraint('uq_user_tender', 'user_tenders', ['user_id', 'tender_id'])
    
    # Drop the new columns
    op.drop_column('user_tenders', 'situation')
    op.drop_column('user_tenders', 'updated_at')
    op.drop_column('user_tenders', 'created_at')
