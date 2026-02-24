"""add lock_version for optimistic locking

Revision ID: f3e1a2d4b7c8
Revises: c2f8f5a7c9d1
Create Date: 2026-02-24 14:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3e1a2d4b7c8"
down_revision = "c2f8f5a7c9d1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lock_version", sa.Integer(), nullable=False, server_default=sa.text("1")))

    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lock_version", sa.Integer(), nullable=False, server_default=sa.text("1")))


def downgrade():
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("lock_version")

    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.drop_column("lock_version")
