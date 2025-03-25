"""TenderType changed to ContractType + bilingual support

Revision ID: e0cb195be6a4
Revises: bad702658d08
Create Date: 2025-03-20 12:03:47.194187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0cb195be6a4'
down_revision: Union[str, None] = 'bad702658d08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Dynamically find and drop all foreign key constraints on user_tender_types
    # SQL Server specific query to find and drop foreign keys
    op.execute("""
    DECLARE @sql NVARCHAR(MAX) = N'';
    
    SELECT @sql += N'
    ALTER TABLE [user_tender_types] DROP CONSTRAINT ' + QUOTENAME(f.name) + ';'
    FROM sys.foreign_keys AS f
    JOIN sys.tables AS t ON f.parent_object_id = t.object_id
    WHERE t.name = 'user_tender_types';
    
    EXEC sp_executesql @sql;
    """)

    # Step 2: Create new contract_types table with bilingual support
    op.create_table('contract_types',
        sa.Column('type_code', sa.String(50), primary_key=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('es_description', sa.String(200), nullable=True)
    )

    # Step 3: Move data from tender_types to contract_types
    op.execute(
        """
        INSERT INTO contract_types (type_code, description)
        SELECT type_code, description FROM tender_types
        """
    )

    # Step 4: Create new user_contract_types association table
    op.create_table('user_contract_types',
        sa.Column('user_criteria_id', sa.Integer(), nullable=False),
        sa.Column('contract_type', sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(['user_criteria_id'], ['user_criteria.id'], ),
        sa.ForeignKeyConstraint(['contract_type'], ['contract_types.type_code'], ),
        sa.PrimaryKeyConstraint('user_criteria_id', 'contract_type')
    )

    # Step 5: Copy data from user_tender_types to user_contract_types
    op.execute(
        """
        INSERT INTO user_contract_types (user_criteria_id, contract_type)
        SELECT user_criteria_id, tender_type FROM user_tender_types
        """
    )

    # Step 6: Drop the old association table
    op.drop_table('user_tender_types')

    # Step 7: Drop any remaining foreign key constraints on tender_types
    op.execute("""
    DECLARE @sql NVARCHAR(MAX) = N'';
    
    SELECT @sql += N'
    ALTER TABLE ' + QUOTENAME(OBJECT_NAME(f.parent_object_id)) + 
    ' DROP CONSTRAINT ' + QUOTENAME(f.name) + ';'
    FROM sys.foreign_keys AS f
    JOIN sys.tables AS t ON f.referenced_object_id = t.object_id
    WHERE t.name = 'tender_types';
    
    IF @sql > ''
        EXEC sp_executesql @sql;
    """)

    # Step 8: Finally drop the old tender_types table
    op.drop_table('tender_types')


def downgrade() -> None:
    # Step 1: Create tender_types table
    op.create_table('tender_types',
        sa.Column('type_code', sa.String(50), primary_key=True),
        sa.Column('description', sa.String(200), nullable=True)
    )

    # Step 2: Copy data from contract_types to tender_types
    op.execute(
        """
        INSERT INTO tender_types (type_code, description)
        SELECT type_code, description FROM contract_types
        """
    )

    # Step 3: Create original user_tender_types association table
    op.create_table('user_tender_types',
        sa.Column('user_criteria_id', sa.Integer(), nullable=False),
        sa.Column('tender_type', sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(['user_criteria_id'], ['user_criteria.id'], ),
        sa.ForeignKeyConstraint(['tender_type'], ['tender_types.type_code'], ),
        sa.PrimaryKeyConstraint('user_criteria_id', 'tender_type')
    )

    # Step 4: Copy data from user_contract_types to user_tender_types
    op.execute(
        """
        INSERT INTO user_tender_types (user_criteria_id, tender_type)
        SELECT user_criteria_id, contract_type FROM user_contract_types
        """
    )

    # Step 5: Drop contract_types association and main tables
    op.drop_table('user_contract_types')
    op.drop_table('contract_types')
