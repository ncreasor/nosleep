"""add saved_analysis_json and saved_changes_json to documents

Revision ID: e2f3a4b5c6d7
Revises: a1b2c3d4e5f7
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("saved_analysis_json", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("saved_changes_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "saved_changes_json")
    op.drop_column("documents", "saved_analysis_json")
