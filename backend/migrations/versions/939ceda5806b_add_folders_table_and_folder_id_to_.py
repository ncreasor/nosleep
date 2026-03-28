"""add folders table and folder_id to documents

Revision ID: 939ceda5806b
Revises: 93fe2378a198
Create Date: 2026-03-28 20:10:05.652511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '939ceda5806b'
down_revision: Union[str, Sequence[str], None] = '93fe2378a198'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create folders table
    op.create_table('folders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('document_type', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_folders_document_type'), 'folders', ['document_type'], unique=False)
    op.create_index(op.f('ix_folders_id'), 'folders', ['id'], unique=False)
    op.create_index(op.f('ix_folders_name'), 'folders', ['name'], unique=False)
    op.create_index(op.f('ix_folders_user_id'), 'folders', ['user_id'], unique=False)

    # Add folder_id to documents using batch mode
    with op.batch_alter_table('documents') as batch_op:
        batch_op.add_column(sa.Column('folder_id', sa.Integer(), nullable=True))
        batch_op.create_index(op.f('ix_documents_folder_id'), ['folder_id'], unique=False)
        batch_op.create_foreign_key('fk_documents_folder_id', 'folders', ['folder_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove folder_id from documents
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_constraint('fk_documents_folder_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_documents_folder_id'))
        batch_op.drop_column('folder_id')

    # Drop folders table
    op.drop_index(op.f('ix_folders_user_id'), table_name='folders')
    op.drop_index(op.f('ix_folders_name'), table_name='folders')
    op.drop_index(op.f('ix_folders_id'), table_name='folders')
    op.drop_index(op.f('ix_folders_document_type'), table_name='folders')
    op.drop_table('folders')
