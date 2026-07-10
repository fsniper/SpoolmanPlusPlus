# Database Challenger Report

## Overview
This report documents the empirical and analytical verification of the Spoolman database models and the Alembic migration script `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py`.

## Challenge Summary
**Overall risk assessment**: MEDIUM

While the migration script and basic model properties function correctly, a potential logic/concurrency issue was discovered regarding how `printer_name` is updated on print jobs that share the same printer object.

## Model Behavior Analysis & Stress Testing

### 1. Automatic Printer Creation on Print Job Addition
- **Mechanism**: The default SQLAlchemy declarative constructor maps keyword arguments to property setters. Setting `printer_name` in `PrintJob(printer_name="Ender 3")` invokes `printer_name.setter`.
- **Code Trace**:
  ```python
  if self.printer is not None:
      self.printer.name = value
  else:
      self.printer = Printer(name=value)
  ```
  Since `self.printer` is initially `None`, it instantiates `Printer(name="Ender 3")` and associates it. SQLAlchemy cascades the insert on database commit.
- **Assessment**: PASS.

### 2. Clearing Printer via `printer_name = None`
- **Mechanism**: Setting `printer_name` to `None` or `""` updates the relationship:
  ```python
  if value is None or value == "":
      self.printer = None
  ```
- **Assessment**: PASS.

### 3. Multiple Print Jobs Pointing to the Same Printer
- **Mechanism**: The relationship in `PrintJob` is many-to-one to `Printer` via `printer_id`. Multiple print jobs can refer to the same `Printer` instance.
- **Assessment**: PASS.

### 4. Risk / Adversarial Challenge: Setter Behavior on Shared Printers
- **Mechanism**: If `job1` and `job2` are both associated with the same printer (e.g. `printer.id = 5` and name = "Ender 3"), updating `job1.printer_name = "Prusa i3"` will execute:
  ```python
  if self.printer is not None:
      self.printer.name = value
  ```
- **Consequence**: This modifies `printer.name` on the shared printer object. This means `job2`'s printer name will automatically change to "Prusa i3" as well.
- **Blast Radius**: Modifying a print job's printer name could inadvertently rename the printer for other print jobs that were pointing to the same printer, instead of moving the current job to a different or new printer.
- **Mitigation**: If the intention was that changing a printer name on a job should assign it to a different printer (creating a new one if it doesn't exist, or linking to an existing one), the setter should search the database. However, since pure SQLAlchemy models do not have database session access, this logic is better moved to the DB layer (`spoolman/database/print_job.py`).

---

## Migration Script Analysis & SQLite Verification

### 1. Upgrade Path (`upgrade`)
- **SQL Compatibility**:
  - The migration uses standard ANSI SQL in raw executes:
    - `SELECT DISTINCT printer_name FROM print_job WHERE printer_name IS NOT NULL AND printer_name != ''`
    - `INSERT INTO printer (registered, name) VALUES (:registered, :name)`
    - `UPDATE print_job SET printer_id = (SELECT id FROM printer WHERE printer.name = print_job.printer_name) WHERE printer_name IS NOT NULL AND printer_name != ''`
  - Columns and foreign keys are added via `op.batch_alter_table` which safely supports SQLite's table recreation requirements.
- **Null and Empty Value Handling**:
  - The migration queries for distinct printer names excluding null/empty strings.
  - Print jobs with null or empty printer names remain with `printer_id = NULL`.
  - The original `printer_name` column is successfully dropped.
- **Assessment**: PASS.

### 2. Downgrade Path (`downgrade`)
- **SQL Compatibility**:
  - Restores the `printer_name` column.
  - Updates using: `UPDATE print_job SET printer_name = (SELECT name FROM printer WHERE printer.id = print_job.printer_id) WHERE printer_id IS NOT NULL`.
  - Drops the `printer_id` column and the `printer` table.
- **Null Value Handling**:
  - For print jobs where `printer_id` was `NULL`, `printer_name` remains `NULL` post-downgrade.
- **Assessment**: PASS.
