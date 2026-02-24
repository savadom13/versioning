"""add deleted items trash table

Revision ID: b81f5f2d9f6c
Revises: 4d7c9f2a1b01
Create Date: 2026-02-24 13:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b81f5f2d9f6c"
down_revision = "4d7c9f2a1b01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deleted_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_by", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("deleted_items")
