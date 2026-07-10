# Implementation Plan: Spoolman Printer Management

## Mission
Build out the full-stack Printer Management feature, migrate existing print jobs to reference a specific printer entity instead of a text field, and update the backend, frontend UI, and integration tests.

## Milestone Decomposition

### Milestone 1: Database Model & Alembic Migration
- **Objective**: Create `printer` database table, link `print_job` to `printer` via `printer_id`, migrate existing `printer_name` to new `printer` table.
- **Tasks**:
  1. Add `Printer` model to `spoolman/database/models.py`.
  2. Add `printer_id` foreign key and relation to `PrintJob` in `spoolman/database/models.py`.
  3. Create and customize Alembic migration:
     - Check if SQLite, Postgres, MySQL support is handled (Alembic's autogenerate + custom migration script).
     - Extract unique `printer_name` from existing `print_job` entries, insert them into `printer` table, map `print_job.printer_id` to `printer.id`, and drop `print_job.printer_name`.
  4. Verify migration applies and database schema validation passes.
- **Verification**: Run `poetry run pytest` (or `poe test`/`poe itest`) and verify schema stability.

### Milestone 2: Backend API and CRUD (IN PROGRESS)
- **Objective**: Implement Python CRUD operations, REST API endpoints, WebSocket notifications, and integration tests for `Printer`.
- **Tasks**:
  1. Define Pydantic models for `Printer` in `spoolman/api/v1/models.py`.
  2. Create CRUD helper routines in `spoolman/database/printer.py`.
  3. Create REST API router in `spoolman/api/v1/printer.py` supporting GET, POST, PATCH, DELETE, and WebSocket updates.
  4. Mount new router in `spoolman/api/v1/router.py`.
  5. Integrate `printer` relationship into `PrintJob` CRUD/API.
  6. Write integration tests in `tests_integration/` to verify CRUD operations, WebSocket events, and relationship with print jobs.
- **Execution Strategy**:
  - Spawn 3 Explorer agents to analyze the codebase and design the API & DB CRUD implementation.
  - Spawn 1 Worker agent to implement the source code changes, run builds, and run integration tests.
  - Spawn 2 Reviewer agents to verify correctness, completeness, and interface compliance.
  - Spawn 2 Challenger agents to run additional validation.
  - Spawn 1 Forensic Auditor to verify code authenticity and integrity.
- **Verification**: Run `poetry run pytest` and verify integration tests pass.

### Milestone 3: Frontend Refine UI (Printers)
- **Objective**: Create React frontend views using Refine and Ant Design for listing, creating, and editing Printers.
- **Tasks**:
  1. Define typescript model `IPrinter` in `client/src/pages/printers/model.tsx`.
  2. Implement `list.tsx` for listing Printers.
  3. Implement `create.tsx` for creating a Printer.
  4. Implement `edit.tsx` for editing a Printer.
  5. Add Printer resource configuration in `client/src/App.tsx` (using `PrinterOutlined` icon).
- **Verification**: Ensure the frontend compiles successfully using `npm run build --prefix client`.

### Milestone 4: Frontend Print Job Integration
- **Objective**: Integrate Printer Select dropdown in Print Job list/create/edit views.
- **Tasks**:
  1. Update `client/src/pages/print_jobs/` list, create, and edit views to use the new `printer` resource.
  2. Replace `printer_name` text input with a searchable select dropdown populated from the Printer API, setting `printer_id`.
  3. Display the selected Printer's name in the Print Job list view.
- **Verification**: Ensure the frontend compiles successfully using `npm run build --prefix client`.

### Milestone 5: E2E and Final Verification
- **Objective**: Verify backend integration tests pass, frontend builds successfully, and there are no integrity issues.
- **Tasks**:
  1. Run full pytest backend test suite.
  2. Build frontend.
  3. Spawn Forensic Auditor to verify integrity and correctness.
