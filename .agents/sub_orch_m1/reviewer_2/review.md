# Database Review & Adversarial Report

## Review Summary

**Verdict**: REQUEST_CHANGES

This review has identified critical data integrity vulnerabilities, major logic inconsistencies, and potential SQLite compatibility failures in the proposed database model changes and Alembic migration script.

---

## Findings

### [Critical] Finding 1: printer_name Setter Renaming Side-Effects
- **What**: Modifying the `printer_name` of an existing print job that shares a `Printer` record with other print jobs will rename that shared `Printer` record in the database.
- **Where**: `spoolman/database/models.py` (lines 179-188)
- **Why**: The setter logic is defined as:
  ```python
  if self.printer is not None:
      self.printer.name = value
  ```
  Since the migration script links multiple existing print jobs to a single shared `Printer` record, updating the printer name of one job mutates the shared `Printer` entity. Consequently, all other print jobs linked to that printer will suddenly change their printer name to the new value.
- **Suggestion**: Avoid inline mutation of the associated printer name in the model setter. Instead, handle printer linking and creation in the database service layer (`spoolman/database/print_job.py`) where a database session is available to search for and link to an existing printer or create a new one.

### [Major] Finding 2: Mismatch in Printer Instance Lifetime (Shared vs. Dedicated)
- **What**: Existing print jobs with duplicate printer names share a single `Printer` record after migration, but new print jobs created via the API receive a separate duplicate `Printer` record for each print job.
- **Where**: `spoolman/database/models.py` (lines 179-188) and `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py` (lines 38-53)
- **Why**: The API creates new jobs using the `printer_name` property, which instantiates a new `Printer(name=value)` every time because the model setter cannot query the database. This duplicates printer records (e.g., 50 print jobs with "Ender 3" will result in 50 separate rows in the `printer` table), defeating the normalization goal of the `printer` table.
- **Suggestion**: Query the `printer` table in `spoolman/database/print_job.py` when creating or updating print jobs. Fetch an existing printer by name and reuse its ID, or insert a new one if none exists.

### [Major] Finding 3: Missing Metadata Naming Conventions Leading to SQLite Downgrade Failures
- **What**: The migration downgrade script attempts to drop a constraint by name: `batch_op.drop_constraint('fk_print_job_printer_id', type_='foreignkey')`.
- **Where**: `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py` (line 76)
- **Why**: SQLite does not support constraint dropping directly and requires table recreation. Because `Base.metadata` has no `naming_convention` defined, SQLite constraints are often reflected without names or with auto-generated names. Alembic will raise a `ValueError` on SQLite because it cannot match the name `'fk_print_job_printer_id'` in the reflected table.
- **Suggestion**: Define a standard naming convention on `Base.metadata` in `spoolman/database/models.py`. Alternatively, omit the explicit `drop_constraint` call on the batch alter block in SQLite, since dropping the `printer_id` column implicitly drops its constraints during the table reconstruction.

### [Minor] Finding 4: Performance and Safety of Migration Subquery Update
- **What**: The migration script runs an `UPDATE` subquery without an index on `printer.name`.
- **Where**: `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py` (lines 49-53)
- **Why**: Running `SELECT id FROM printer WHERE printer.name = print_job.printer_name` for every row in `print_job` requires a full table scan of the `printer` table for each row in `print_job`. Additionally, if duplicate names occur (due to database collation differences), this query will raise a cardinality violation error on MySQL/PostgreSQL.
- **Suggestion**: Use `LIMIT 1` in the subquery to prevent crashes, or create a temporary index on `printer.name` during migration.

---

## Verified Claims

- **Migration script structure (using `batch_alter_table`)** → verified via `view_file` → **PASS** (syntactically correct and uses batch blocks for SQLite compatibility).
- **SQLite nullable foreign key support** → verified via code inspection → **PASS** (the models correctly define `printer_id` as nullable).

---

## Coverage Gaps

- **Integration test coverage** — risk level: **Medium** — recommendation: Run the backend integration tests. Due to terminal permission timeout, live verification could not be executed. However, static code analysis shows that the existing test suite does not cover multi-job printer sharing/renaming side-effects.

---

## Unverified Items

- **Backend test suite execution** — reason not verified: Terminal commands were not approved within the timeout period.

---
---

# Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: HIGH

---

## Challenges

### [Critical] Challenge 1: Data Corruption via Printer Renaming
- **Assumption challenged**: Modifying a print job's printer name only affects that print job.
- **Attack scenario**:
  1. System has 50 historical print jobs linked to a single printer "Ender 3" (ID 1).
  2. A user edits the printer name on print job #50 to "Ender 3 Neo".
  3. The model's setter executes `self.printer.name = "Ender 3 Neo"`.
  4. The shared printer record is updated, silently changing the printer name of the other 49 historical print jobs.
- **Blast radius**: High. Corruption of historical print job metadata.
- **Mitigation**: Decouple the printer name change from the shared `Printer` entity. Query/create the printer inside the service layer (`spoolman/database/print_job.py`) instead of inside the model setter.

### [High] Challenge 2: Duplicate Printers from API
- **Assumption challenged**: The `printer` table represents a normalized collection of printers.
- **Attack scenario**:
  1. A client submits 100 print jobs, all specifying `"printer_name": "Ender 3"`.
  2. Because the setter always instantiates a new `Printer(name=value)` when `self.printer` is None, the database creates 100 separate printer rows with the name "Ender 3".
- **Blast radius**: Medium. Loss of normalization benefits, database bloating, and breaks future printer list features.
- **Mitigation**: Perform a lookup in `spoolman/database/print_job.py` when creating or updating print jobs.

### [High] Challenge 3: Migration Rollback Failure on SQLite
- **Assumption challenged**: The migration downgrade works seamlessly on SQLite.
- **Attack scenario**:
  1. A user on SQLite attempts to downgrade the migration.
  2. Alembic executes `batch_op.drop_constraint('fk_print_job_printer_id', type_='foreignkey')`.
  3. Because no metadata-level naming convention is defined, Alembic fails to match `'fk_print_job_printer_id'` in the reflected SQLite schema.
  4. The downgrade crashes, leaving the database schema inconsistent.
- **Blast radius**: High. Unstable migrations on the default SQLite database.
- **Mitigation**: Add a naming convention to SQLAlchemy's `Base.metadata`.

---

## Stress Test Results

- **Multiple print jobs sharing same printer** → Rename printer on one job → Updates all other print jobs sharing that printer → **FAIL** (unexpected side-effect).
- **Multiple creations with same printer name** → Creates duplicate rows in `printer` table → **FAIL** (violates normalization).
- **SQLite downgrade execution** → Drop constraint on SQLite table without metadata naming convention → Potential crash/ValueError → **FAIL**.

---

## Unchallenged Areas

- **Frontend-backend websocket events** — reason not challenged: Out of scope of database models and migration review.
