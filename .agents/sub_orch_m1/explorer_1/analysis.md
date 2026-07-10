# Spoolman Database Models & Alembic Migration Investigation

This report provides a detailed analysis of Spoolman's database models, its Alembic migration structure, and a concrete proposal for implementing the `Printer` model and the corresponding database migration.

---

## 1. Analysis of Spoolman Database Models

The database models in Spoolman are defined in `spoolman/database/models.py`.

### 1.1 Structure & Imports
Spoolman uses **SQLAlchemy 2.0 Declarative Mappings** (specifically using the `Mapped` and `mapped_column` pattern). The base model class is defined as:
```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

class Base(AsyncAttrs, DeclarativeBase):
    pass
```

The imports used for the database models include:
- `datetime` from standard library.
- `Optional` from `typing`.
- `ForeignKey`, `Integer`, `String`, `Text` from `sqlalchemy`.
- `AsyncAttrs` from `sqlalchemy.ext.asyncio`.
- `DeclarativeBase`, `Mapped`, `mapped_column`, `relationship` from `sqlalchemy.orm`.

### 1.2 Key Patterns for Fields and Relationships
- **Primary Keys:** Declared using `Mapped[int] = mapped_column(primary_key=True, index=True)`.
- **String Columns:** Standard varchar columns are defined with specific lengths, e.g., `name: Mapped[str] = mapped_column(String(64))` or `comment: Mapped[str | None] = mapped_column(String(1024))`.
- **Date/Time Columns:** Defined as `registered: Mapped[datetime] = mapped_column()`.
- **Relationships:** Established using `relationship` with `back_populates` to reference inverse relationships, e.g., `filaments: Mapped[list["Filament"]] = relationship(back_populates="vendor")` and `vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="filaments")`.

---

## 2. Alembic Migration Setup and Operations

### 2.1 Configuration
- The main Alembic configuration is located in `alembic.ini` in the project root.
- The configuration references the `migrations` directory (`script_location = migrations`).
- Version filenames are generated using the template: `%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s`.

### 2.2 Migrations Execution
- During startup, Spoolman programmatically runs migrations by spawning a subprocess calling `alembic upgrade head` in `spoolman/main.py`. This is done to prevent process hangs with the uvicorn worker.
- Migrations can be manually run using standard CLI: `alembic upgrade head`.
- Migrations are generated using standard command: `alembic revision --autogenerate -m "migration_name"`.

---

## 3. Database Migration Requirement Analysis & Proposal

To meet the user requirements, we must add the `Printer` model, modify the `PrintJob` model, and construct a database-agnostic Alembic migration.

### 3.1 Model Changes (`spoolman/database/models.py`)

#### Proposed `Printer` Model
```python
class Printer(Base):
    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(256))
    model: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(String(1024))
    
    # Relationship back to PrintJob
    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")
```

#### Modified `PrintJob` Model
- Remove the `printer_name` column.
- Add `printer_id` as a foreign key column referencing `printer.id`.
- Add `printer` relationship referencing `Printer`.

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
    
    # New columns/relationships
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"))
    printer: Mapped[Optional["Printer"]] = relationship(back_populates="print_jobs")
    
    comment: Mapped[str | None] = mapped_column(String(1024))
    spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
```

---

### 3.2 Database-Agnostic Migration Proposal

The migration needs to support multiple databases (SQLite, PostgreSQL, MySQL, CockroachDB). Due to limitations in SQLite, we must use batch operations.

#### Proposed Alembic Migration Script (`migrations/versions/<date>_add_printer_table.py`)

```python
"""Add printer table and migrate printer_name to printer_id.

Revision ID: <generated_id>
Revises: fdc4cb99d052
Create Date: 2026-07-10 16:15:00
"""

from datetime import datetime
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "new_revision_id"
down_revision = "fdc4cb99d052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Perform the upgrade."""
    # 1. Create the printer table
    op.create_table(
        "printer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registered", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=True),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("comment", sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_printer_id"), "printer", ["id"], unique=False)

    # 2. Add printer_id foreign key column to print_job using batch alter
    # batch_alter_table is necessary for SQLite compatibility
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column("printer_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_print_job_printer_id", "printer", ["printer_id"], ["id"])

    # 3. Data Migration: Populate the printer table and link existing print jobs
    bind = op.get_bind()
    metadata = sa.MetaData()

    # Define tables locally for SQLAlchemy Core query generation
    print_job_table = sa.Table(
        "print_job",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("printer_name", sa.String(length=256)),
        sa.Column("printer_id", sa.Integer()),
    )
    
    printer_table = sa.Table(
        "printer",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("registered", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
    )

    # Query all unique, non-empty, and non-null printer names from print_job
    select_query = sa.select(print_job_table.c.printer_name).where(
        print_job_table.c.printer_name.isnot(None),
        print_job_table.c.printer_name != ""
    ).distinct()
    
    results = bind.execute(select_query).fetchall()
    unique_names = [row[0] for row in results if row[0]]

    if unique_names:
        current_time = datetime.utcnow().replace(microsecond=0)
        
        # Insert all printers
        for name in unique_names:
            insert_stmt = printer_table.insert().values(
                registered=current_time,
                name=name
            )
            bind.execute(insert_stmt)
            
        # Select all inserted printers back to map names to their newly generated database IDs.
        # This avoid driver-specific primary key extraction issues (e.g., inserted_primary_key).
        select_printers = sa.select(printer_table.c.id, printer_table.c.name)
        printers = bind.execute(select_printers).fetchall()
        
        # Update references in print_job
        for p_id, p_name in printers:
            update_stmt = (
                sa.update(print_job_table)
                .where(print_job_table.c.printer_name == p_name)
                .values(printer_id=p_id)
            )
            bind.execute(update_stmt)

    # 4. Drop the obsolete printer_name column from print_job
    # This must be run inside batch_alter_table to recreate the table on SQLite
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_column("printer_name")


def downgrade() -> None:
    """Perform the downgrade."""
    # 1. Add printer_name column back to print_job
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.add_column(sa.Column("printer_name", sa.String(length=256), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()
    
    print_job_table = sa.Table(
        "print_job",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("printer_name", sa.String(length=256)),
        sa.Column("printer_id", sa.Integer()),
    )
    
    printer_table = sa.Table(
        "printer",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=256)),
    )

    # 2. Restore printer_name from the printer table using a subquery
    subquery = sa.select(printer_table.c.name).where(printer_table.c.id == print_job_table.c.printer_id).scalar_subquery()
    update_stmt = sa.update(print_job_table).values(printer_name=subquery).where(print_job_table.c.printer_id.isnot(None))
    bind.execute(update_stmt)

    # 3. Remove printer_id and its foreign key constraint from print_job
    with op.batch_alter_table("print_job") as batch_op:
        batch_op.drop_constraint("fk_print_job_printer_id", type_="foreignkey")
        batch_op.drop_column("printer_id")

    # 4. Drop the printer table and its index
    op.drop_index(op.f("ix_printer_id"), table_name="printer")
    op.drop_table("printer")
```

### 3.3 Database-Agnostic Handling Rationale

1. **SQLite Support with `batch_alter_table`:** Standard SQLite does not support dropping columns or adding foreign keys to existing tables easily. Using Alembic's `with op.batch_alter_table("print_job") as batch_op:` ensures that Alembic executes these schema changes by creating a temporary table, copying data, and replacing the old table.
2. **Robust ID Mapping Strategy:** Instead of relying on `cursor.inserted_primary_key`, which behaves differently across async drivers (e.g. `aiosqlite` vs `asyncpg` vs `aiomysql`), this migration inserts all unique printers and then queries them back. This decouples the primary key retrieval from driver-level behavior, making it fully portable.
3. **CockroachDB / PostgreSQL / MySQL Compatibility:** Standard SQLAlchemy core expressions (like `sa.select`, `sa.update`, `sa.insert`) dynamically compile to the dialect-specific SQL of the active database connection. No raw SQL strings are executed.
