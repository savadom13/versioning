"""replace objects with signals and assets

Revision ID: 4d7c9f2a1b01
Revises: 2234f021db61
Create Date: 2026-02-24 12:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d7c9f2a1b01"
down_revision = "2234f021db61"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False),
        sa.Column("modulation", sa.String(length=50), nullable=False),
        sa.Column("power", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "asset_signals",
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ),
        sa.PrimaryKeyConstraint("asset_id", "signal_id"),
    )

    op.drop_table("objects")


def downgrade():
    op.create_table(
        "objects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_table("asset_signals")
    op.drop_table("signals")
    op.drop_table("assets")
