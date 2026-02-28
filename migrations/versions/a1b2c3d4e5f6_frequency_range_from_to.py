"""frequency as range (frequency_from, frequency_to)

Revision ID: a1b2c3d4e5f6
Revises: f3e1a2d4b7c8
Create Date: 2026-02-28

"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f3e1a2d4b7c8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("frequency_from", sa.Float(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("frequency_to", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.execute(sa.text("UPDATE signals SET frequency_from = frequency, frequency_to = frequency"))
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.drop_column("frequency")
        batch_op.create_check_constraint("ck_signals_frequency_range", "frequency_to >= frequency_from")


def downgrade():
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.drop_constraint("ck_signals_frequency_range", type_="check")
        batch_op.add_column(sa.Column("frequency", sa.Float(), nullable=False, server_default=sa.text("0")))
    op.execute(sa.text("UPDATE signals SET frequency = frequency_from"))
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.drop_column("frequency_to")
        batch_op.drop_column("frequency_from")
