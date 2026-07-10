# Spoolman Database Models and Migration Structure Analysis

This report presents findings from the read-only investigation of the Spoolman database models and Alembic migration structure.

---

## 1. Analysis of Existing Models (`spoolman/database/models.py`)

### Structural Patterns
- **Base Class**: Models inherit from `Base` which inherits from `AsyncAttrs` and `DeclarativeBase` to leverage SQLAlchemy 2.0 features (such as 2.0 type-annotated mapping with `Mapped` and asynchronous attribute access).
- **Table Name**: Indicated via `__tablename__` (e.g., `__tablename__ = "print_job"`).
- **Primary Keys**: Defined with `mapped_column(primary_key=True, index=True)` (typically on `id: Mapped[int]`).
- **Data Types**: Common columns map to SQLAlchemy types via type annotations (`Mapped[type]`) and optional `mapped_column` configuration (e.g. `String(256)`, `String(1024)` for strings, `datetime` for timestamps).
- **Foreign Keys**: Specified using `mapped_column(ForeignKey("table.id"))`.
- **Relationships**: Configured bidirectionally using `relationship(back_populates="...")`.
- **Nullability**: In SQLAlchemy 2.0, standard annotations like `Mapped[str]` result in `nullable=False`, while optional type annotations like `Mapped[str | None]` or `Mapped[Optional[str]]` resolve to `nullable=True`.

### Imports Used
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
```

---

## 2. Alembic Config and Migration Flow

### File Structure
- **Config file**: `alembic.ini` is located in the project root directory.
  - Specifies `script_location = migrations` and custom filename formatting: `file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s`.
- **Scripts location**: `migrations/` directory contains:
  - `env.py`: Setup environment. Reads DB connection URL from `spoolman.database.database.get_connection_url()` and connects dynamically. Supports both online and offline migration runs.
  - `script.py.mako`: Template for generating new migrations.
  - `versions/`: Directory containing all migration version scripts (e.g., `2026_07_08_2312-fdc4cb99d052_add_print_management.py`).

### How Migration is Generated and Run
- **Generation**: Developers generate migrations using Alembic CLI:
  ```bash
  alembic revision --autogenerate -m "Add printer table"
  ```
- **Execution**: Migrations are run automatically at application startup. In `spoolman/main.py`, a subprocess runs `alembic upgrade head` before starting the FastAPI/uvicorn server. This avoids hanging issues caused by uvicorn worker threads.

---

## 3. Database Migration Requirement Analysis

### Proposed Code Changes in `spoolman/database/models.py`

#### A. Add the `Printer` Model
```python
class Printer(Base):
    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(256))
    model: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(String(1024))

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")
```

#### B. Update the `PrintJob` Model
Modify `PrintJob` to replace `printer_name` with `printer_id` and the `printer` relationship:
```python
class PrintJob(Base):
    __tablename__ = "print_job"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"))
    plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
    status: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[datetime | None] = mapped_column()
    end_time: Mapped[datetime | None] = mapped_column()
    
    # NEW FIELDS:
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"))
    printer: Mapped[Optional["Printer"]] = relationship(back_populates="print_jobs")
    
    comment: Mapped[str | None] = mapped_column(String(1024))
    spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
```

---

## 4. Custom Alembic Migration Strategy (Cross-Dialect)

Because Spoolman supports SQLite, PostgreSQL, and MySQL, the migration must handle limitations unique to SQLite (e.g. inability to drop columns or add foreign keys without recreating tables). Using Alembic's `op.batch_alter_table` ensures operations on `print_job` are performed via shadow-table copy on SQLite while generating standard `ALTER TABLE` statements on PostgreSQL and MySQL.

Furthermore, database-specific query structures for data insertion are avoided by querying the existing `printer_name` values, inserting the unique values, reading back the map of `name -> id`, and updating `print_job` inside transaction context using cross-dialect SQLAlchemy Core commands.

### Migration Script Proposal (`migrations/versions/<timestamp>_add_printer.py`)

```python
"""add printer and migrate printjob data

Revision ID: <generated_id>
Revises: fdc4cb99d052
Create Date: 2026-07-10 16:15:00.000000
"""

import datetime
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'next_revision_id'
down_revision = 'fdc4cb99d052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the new 'printer' table
    op.create_table(
        'printer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('registered', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('model', sa.String(length=256), nullable=True),
        sa.Column('location', sa.String(length=64), nullable=True),
        sa.Column('comment', sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_printer_id'), 'printer', ['id'], unique=False)

    # 2. Add 'printer_id' foreign key column to 'print_job' using batch_alter_table
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column('printer_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_print_job_printer_id_printer', 'printer', ['printer_id'], ['id'])

    # 3. Migrate printer_name values to new printer table
    connection = op.get_bind()

    # Define temporary table structures for Core operations
    print_job_table = sa.Table(
        'print_job',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('printer_name', sa.String(256)),
        sa.Column('printer_id', sa.Integer),
    )

    printer_table = sa.Table(
        'printer',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('registered', sa.DateTime),
        sa.Column('name', sa.String(256)),
    )

    # Select unique, non-empty printer names from print_job
    select_stmt = sa.select(print_job_table.c.printer_name).distinct().where(
        print_job_table.c.printer_name.is_not(None),
        print_job_table.c.printer_name != ''
    )
    results = connection.execute(select_stmt).all()
    unique_names = [row[0] for row in results]

    if unique_names:
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
        # Insert a new printer for each unique printer_name
        for name in unique_names:
            insert_stmt = printer_table.insert().values(
                registered=now,
                name=name
            )
            connection.execute(insert_stmt)

        # Retrieve mapped IDs to update print_job table
        select_printers = sa.select(printer_table.c.id, printer_table.c.name)
        printer_rows = connection.execute(select_printers).all()
        name_to_id = {row[1]: row[0] for row in printer_rows}

        # Update printer_id in print_job matching by name
        for name, printer_id in name_to_id.items():
            update_stmt = (
                sa.update(print_job_table)
                .where(print_job_table.c.printer_name == name)
                .values(printer_id=printer_id)
            )
            connection.execute(update_stmt)

    # 4. Drop 'printer_name' column from 'print_job' using batch_alter_table
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_column('printer_name')


def downgrade() -> None:
    # 1. Re-add 'printer_name' column to 'print_job' using batch_alter_table
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column('printer_name', sa.String(length=256), nullable=True))

    # 2. Reverse migrate printer names back from printer table to print_job.printer_name
    connection = op.get_bind()

    print_job_table = sa.Table(
        'print_job',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('printer_name', sa.String(256)),
        sa.Column('printer_id', sa.Integer),
    )

    printer_table = sa.Table(
        'printer',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(256)),
    )

    select_printers = sa.select(printer_table.c.id, printer_table.c.name)
    printer_rows = connection.execute(select_printers).all()
    id_to_name = {row[0]: row[1] for row in printer_rows}

    for printer_id, name in id_to_name.items():
        update_stmt = (
            sa.update(print_job_table)
            .where(print_job_table.c.printer_id == printer_id)
            .values(printer_name=name)
        )
        connection.execute(update_stmt)

    # 3. Drop 'printer_id' foreign key and column from 'print_job' using batch_alter_table
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_constraint('fk_print_job_printer_id_printer', type_='foreignkey')
        batch_op.drop_column('printer_id')

    # 4. Drop printer table and index
    op.drop_index(op.f('ix_printer_id'), table_name='printer')
    op.drop_table('printer')
```
