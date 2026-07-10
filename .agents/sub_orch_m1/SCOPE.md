# Scope: Milestone 1 - Database Model & Alembic Migration

## Architecture
- SQLAlchemy models are defined in `spoolman/database/models.py`.
- Migration scripts are in `spoolman/database/migrations/versions/`.
- Alembic configuration is in the project root.
- A new model `Printer` will be added, and the existing `PrintJob` model will be modified to reference `Printer`.
- Migration will migrate data from `print_job.printer_name` to the new `Printer` table, set the foreign keys, and drop `printer_name`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | DB Model Changes | Define Printer model and modify PrintJob in `models.py` | None | DONE |
| 2 | Migration Script | Generate and customize Alembic migration | M1 | DONE |
| 3 | Validation & Tests | Verify migration runs and all tests pass | M1, M2 | DONE |

## Interface Contracts
### Models
- `Printer`:
  - `id`: integer primary key
  - `registered`: datetime, default UTC now
  - `name`: string, required, non-empty
  - `model`: string, nullable
  - `location`: string, nullable
  - `comment`: string, nullable
- `PrintJob`:
  - `printer_id`: integer, nullable foreign key to `printer.id`
  - `printer`: relationship to `Printer`, nullable
