"""switch to soft delete flags on entities

Revision ID: c2f8f5a7c9d1
Revises: b81f5f2d9f6c
Create Date: 2026-02-24 13:40:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2f8f5a7c9d1"
down_revision = "b81f5f2d9f6c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deleted_by", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_signals_is_deleted"), ["is_deleted"], unique=False)

    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deleted_by", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_assets_is_deleted"), ["is_deleted"], unique=False)

    op.drop_table("deleted_items")


def downgrade():
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

    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_assets_is_deleted"))
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")

    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_signals_is_deleted"))
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
