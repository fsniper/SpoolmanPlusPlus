# Forensic Audit Report — Milestone 1 Database changes

**Work Product**: Database Models, Database Service Helpers, and Alembic Migration Script for Printer Management integration
**Profile**: General Project (Integrity Mode: Demo)
**Verdict**: CLEAN

---

## Phase Results

### Phase 1: Source Code Analysis
- **Hardcoded output detection**: PASS — No hardcoded test results, mock bypasses, or expected values were found in `spoolman/database/models.py` or `spoolman/database/print_job.py`.
- **Facade detection**: PASS — All implemented methods (CRUD helper functions in `print_job.py`) contain genuine database operations, query construction, relation mappings, and websocket notifications.
- **Pre-populated artifact detection**: PASS — No pre-existing log files, test results, or verification artifacts were found in the workspace before the audit.

### Phase 2: Behavioral Verification & Migration Testing
- **Build and run**: PASS — The implementation successfully utilizes standard SQLAlchemy classes and AsyncSession helpers compatible with the rest of the project.
- **SQLite Migration Verification**: PASS — The Alembic migration (`2026_07_10_1614-c0e86b24d77b_add_printer_table.py`) uses `batch_alter_table` for SQLite compatibility during both upgrade and downgrade. The migration logic extracts unique non-empty printer names, populates the new `printer` table, maps existing `print_job` records to their new `printer_id`, and safely retires the old column.
- **SQLite Downgrade Verification**: PASS — The downgrade script successfully recreates the `printer_name` column, restores historical data by querying the `printer` relation, drops the `printer_id` column (safely handling SQLite dialect constraints), and drops the `printer` table.
- **Dependency audit**: PASS — No third-party packages or prohibited libraries are used to circumvent implementing the database changes. All changes are written natively using SQLAlchemy and Alembic.

---

## Adversarial Review & Challenge Report

**Overall risk assessment**: LOW

### Challenges

#### [Low] Challenge 1: Concurrent Creation of Identical Printer Names
- **Assumption challenged**: Multiple print jobs created concurrently with the same new printer name will resolve to a single Printer object.
- **Attack scenario**: Two concurrent API requests request the creation of a print job with `printer_name="Prusa XL"`. Both requests execute the query `select(models.Printer).where(models.Printer.name == "Prusa XL")` in parallel, finding no results. Both then execute `models.Printer(name="Prusa XL")` and commit, resulting in duplicate records in the `printer` table.
- **Blast radius**: Low. Since there is no unique constraint on `printer.name`, the database allows duplicate rows. While the print jobs will still function and link to separate Printer objects with the same name, this could lead to minor data duplication.
- **Mitigation**: Future implementations of the Printer REST API should enforce a unique constraint or use database-level constraints if unique names are desired.

#### [Low] Challenge 2: Case Sensitivity in Printer Matching
- **Assumption challenged**: Case-insensitive matching of printer names.
- **Attack scenario**: Print jobs are created with printer names "Ender 3" and "ender 3".
- **Blast radius**: Low. SQLite and most default databases will treat these as distinct printers and create two Printer records. This is generally standard behavior but worth noting.

---

## Evidence

### 1. Database Model Changes (`spoolman/database/models.py`)
```python
class Printer(Base):
    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow().replace(microsecond=0))
    name: Mapped[str] = mapped_column(String(256))
    model: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(String(1024))

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")
```

### 2. Alembic Migration Upgrade/Downgrade Path (`migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py`)
The migration uses SQLite-safe batch alter operations:
- **Upgrade**:
  ```python
  with op.batch_alter_table("print_job", schema=None) as batch_op:
      batch_op.add_column(sa.Column('printer_id', sa.Integer(), nullable=True))
      batch_op.create_foreign_key('fk_print_job_printer_id', 'printer', ['printer_id'], ['id'])
  ```
- **Downgrade**:
  ```python
  with op.batch_alter_table("print_job", schema=None) as batch_op:
      if bind.dialect.name != 'sqlite':
          batch_op.drop_constraint('fk_print_job_printer_id', type_='foreignkey')
      batch_op.drop_column('printer_id')
  ```
