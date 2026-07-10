# Spoolman Database Models & Alembic Migration Analysis

This analysis outlines the architecture of Spoolman's database models, describes the configuration and execution flow of Alembic migrations, and details the design of the database migration for introducing a `Printer` model and updating the `PrintJob` model.

---

## 1. Analysis of Existing Database Models

The existing SQLAlchemy models are defined in `spoolman/database/models.py`.

### Structure & Layout
* **Base Declarative Class**: All models inherit from `Base`, which is defined as:
  ```python
  class Base(AsyncAttrs, DeclarativeBase):
      pass
  ```
  It leverages `AsyncAttrs` from `sqlalchemy.ext.asyncio` for asynchronous attribute access and SQLAlchemy 2.0 style `DeclarativeBase`.
* **Field Declarations**: Spoolman uses SQLAlchemy 2.0 Type-Annotated mapping format (`Mapped[...]` and `mapped_column()`).
  * Non-nullable columns are mapped using `Mapped[type]`.
  * Nullable columns are mapped using `Mapped[type | None]`.
  * Primary keys use `primary_key=True` and `index=True` configuration.
  * Relationships are declared via `Mapped[...] = relationship(...)` with corresponding `back_populates` configuration.

### Imports Used in `models.py`
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
```

### Reference Case: `PrintJob` Model
Currently, `PrintJob` is defined as:
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
    printer_name: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(String(1024))
    spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
```

---

## 2. Alembic Configuration & Migration Pipeline

### Locations
* **Configuration File**: `alembic.ini` is located in the project root directory.
* **Migration Directory**: `migrations/` in the project root.
* **Migration Scripts**: Found under `migrations/versions/` (e.g., `2026_07_08_2312-fdc4cb99d052_add_print_management.py`).

### How Migrations are Generated
New migrations are generated from the command line using Alembic's CLI from the project root:
```bash
# In the project root (using the virtual environment manager, e.g., uv)
uv run alembic revision --autogenerate -m "add_printer_management"
```

### How Migrations are Executed
1. **Automatic Runtime Migration**: When Spoolman starts up, the application runner in `spoolman/main.py` automatically checks for and executes pending migrations in a subprocess:
   ```python
   project_root = Path(__file__).parent.parent
   subprocess.run(["alembic", "upgrade", "head"], check=True, cwd=project_root)
   ```
2. **Manual Execution**: Developers can apply migrations manually via command line:
   ```bash
   uv run alembic upgrade head
   ```

---

## 3. Database Migration Requirement Analysis

### Proposed SQLAlchemy Model Changes

We need to add a new `Printer` class in `spoolman/database/models.py` and modify `PrintJob`.

#### Add `Printer` Model
```python
class Printer(Base):
    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(256))
    model: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(String(1024))

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")
```

#### Update `PrintJob` Model
In `spoolman/database/models.py`, replace `printer_name` on `PrintJob` with:
```python
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"))
    printer: Mapped[Optional["Printer"]] = relationship(back_populates="print_jobs")
```

---

## 4. Customized Alembic Migration Script Design

To guarantee safety across all supported backends (SQLite, PostgreSQL, MySQL), we must:
1. Ensure table additions and alterations are executed using Alembic's `op.batch_alter_table` context. SQLite does not support standard `ALTER TABLE` modifications, so using explicit batch mode renders it safe for SQLite while acting as standard `ALTER` statements for MySQL/PostgreSQL.
2. Structure the data migration using set-based SQL queries rather than nested database roundtrips, reducing transaction time and making it 100% database-agnostic.

Here is the recommended python migration file code:

```python
"""add printer management.

Revision ID: <generated_revision_id>
Revises: fdc4cb99d052
Create Date: 2026-07-10 16:30:00.000000
"""

import datetime
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '<generated_revision_id>'
down_revision = 'fdc4cb99d052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the printer table
    op.create_table(
        "printer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registered", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("comment", sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_printer_id"), "printer", ["id"], unique=False)

    # 2. Add printer_id foreign key column to print_job (nullable)
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column("printer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_print_job_printer", "printer", ["printer_id"], ["id"])

    # 3. Perform data migration (set-based and database-agnostic)
    bind = op.get_bind()
    print_job_table = sa.Table(
        "print_job",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("printer_name", sa.String(length=256)),
        sa.Column("printer_id", sa.Integer),
    )
    printer_table = sa.Table(
        "printer",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("registered", sa.DateTime),
        sa.Column("name", sa.String(length=256)),
    )

    # Insert distinct printer names from print_job into printer
    current_time = datetime.datetime.utcnow().replace(microsecond=0)
    insert_stmt = sa.insert(printer_table).from_select(
        ["registered", "name"],
        sa.select(
            sa.literal(current_time).label("registered"),
            print_job_table.c.printer_name.label("name")
        ).where(
            print_job_table.c.printer_name.isnot(None),
            print_job_table.c.printer_name != ""
        ).distinct()
    )
    bind.execute(insert_stmt)

    # Update print_job's printer_id where printer_name matches printer name
    subquery = sa.select(printer_table.c.id).where(printer_table.c.name == print_job_table.c.printer_name).scalar_subquery()
    update_stmt = sa.update(print_job_table).values(printer_id=subquery).where(
        print_job_table.c.printer_name.isnot(None),
        print_job_table.c.printer_name != ""
    )
    bind.execute(update_stmt)

    # 4. Drop the printer_name column from print_job
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_column("printer_name")


def downgrade() -> None:
    # 1. Re-add printer_name column to print_job
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column("printer_name", sa.String(length=256), nullable=True))

    # 2. Restore printer_name from the printer table
    bind = op.get_bind()
    print_job_table = sa.Table(
        "print_job",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("printer_name", sa.String(length=256)),
        sa.Column("printer_id", sa.Integer),
    )
    printer_table = sa.Table(
        "printer",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=256)),
    )

    subquery = sa.select(printer_table.c.name).where(printer_table.c.id == print_job_table.c.printer_id).scalar_subquery()
    update_stmt = sa.update(print_job_table).values(printer_name=subquery).where(
        print_job_table.c.printer_id.isnot(None)
    )
    bind.execute(update_stmt)

    # 3. Drop printer_id column and foreign key constraint from print_job
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_constraint("fk_print_job_printer", type_="foreignkey")
        batch_op.drop_column("printer_id")

    # 4. Drop printer table
    op.drop_index(op.f("ix_printer_id"), table_name="printer")
    op.drop_table("printer")
```

---

## 5. Summary of Downstream Changes

Replacing `printer_name` with a structured `Printer` model will require downstream refactorings across the codebase:
1. **Pydantic schemas**:
   * Add a new `Printer` schema class in `spoolman/api/v1/models.py` (with creation, update, and response shapes).
   * Update the `PrintJob` Pydantic model to use `printer_id: int | None` instead of `printer_name: str | None`.
2. **Database Helper Functions (`spoolman/database/print_job.py`)**:
   * Change `printer_name` parameters to `printer_id` in `create()` and `update()`.
   * Add verification logic to ensure target printer exists (e.g. `await printer.get_by_id(db, printer_id)`).
   * Implement a new helper module `spoolman/database/printer.py` to support CRUD operations on the `printer` table.
3. **API Router Endpoints**:
   * Add a new router module `spoolman/api/v1/printer.py` and register it in `spoolman/api/v1/router.py`.
4. **Integration Tests (`tests_integration/tests/print_job/test_crud.py`)**:
   * Modify the payload structure in tests to create a test printer first, capture its `id`, and assign it to the print jobs.
