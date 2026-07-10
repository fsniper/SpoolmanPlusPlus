"""add printer table.

Revision ID: c0e86b24d77b
Revises: fdc4cb99d052
Create Date: 2026-07-10 16:14:00.000000
"""

from datetime import datetime
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c0e86b24d77b'
down_revision = 'fdc4cb99d052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Perform the upgrade."""
    # 1. Create printer table
    op.create_table('printer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('registered', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('model', sa.String(length=256), nullable=True),
        sa.Column('location', sa.String(length=256), nullable=True),
        sa.Column('comment', sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_printer_id'), 'printer', ['id'], unique=False)

    # 2. Add printer_id to print_job
    with op.batch_alter_table("print_job", schema=None) as batch_op:
        batch_op.add_column(sa.Column('printer_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_print_job_printer_id', 'printer', ['printer_id'], ['id'])

    # 3. Data migration
    bind = op.get_bind()
    results = bind.execute(sa.text("SELECT DISTINCT printer_name FROM print_job WHERE printer_name IS NOT NULL AND printer_name != ''")).fetchall()
    names = [row[0] for row in results]
    now = datetime.utcnow().replace(microsecond=0)
    for name in names:
        bind.execute(
            sa.text("INSERT INTO printer (registered, name) VALUES (:registered, :name)"),
            {"registered": now, "name": name}
        )
    if names:
        bind.execute(sa.text(
            "UPDATE print_job "
            "SET printer_id = (SELECT id FROM printer WHERE printer.name = print_job.printer_name) "
            "WHERE printer_name IS NOT NULL AND printer_name != ''"
        ))

    # 4. Drop printer_name from print_job
    with op.batch_alter_table("print_job", schema=None) as batch_op:
        batch_op.drop_column('printer_name')


def downgrade() -> None:
    """Perform the downgrade."""
    # 1. Add printer_name back to print_job
    with op.batch_alter_table("print_job", schema=None) as batch_op:
        batch_op.add_column(sa.Column('printer_name', sa.String(length=256), nullable=True))

    # 2. Data migration (restore printer_name from printer)
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE print_job "
        "SET printer_name = (SELECT name FROM printer WHERE printer.id = print_job.printer_id) "
        "WHERE printer_id IS NOT NULL"
    ))

    # 3. Drop printer_id column and foreign key constraint from print_job
    with op.batch_alter_table("print_job", schema=None) as batch_op:
        if bind.dialect.name != 'sqlite':
            batch_op.drop_constraint('fk_print_job_printer_id', type_='foreignkey')
        batch_op.drop_column('printer_id')

    # 4. Drop printer table and index
    op.drop_index(op.f('ix_printer_id'), table_name='printer')
    op.drop_table('printer')
