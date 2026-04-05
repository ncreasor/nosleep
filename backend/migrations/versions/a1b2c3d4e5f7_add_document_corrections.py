"""add document_corrections table

Revision ID: a1b2c3d4e5f7
Revises: 491fa0d17bea
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "491fa0d17bea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("error_id", sa.String(length=64), nullable=True),
        sa.Column("error_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_corrections_document_id"),
        "document_corrections",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_corrections_user_id"),
        "document_corrections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_corrections_error_id"),
        "document_corrections",
        ["error_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_corrections_error_type"),
        "document_corrections",
        ["error_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_corrections_created_at"),
        "document_corrections",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_corrections_created_at"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_error_type"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_error_id"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_user_id"), table_name="document_corrections")
    op.drop_index(op.f("ix_document_corrections_document_id"), table_name="document_corrections")
    op.drop_table("document_corrections")
