# Handoff Report: Milestone IMP-1: Backend API & CRUD Analysis

## 1. Observation

Direct observations in the codebase and test files:
- **Database Models**: In `spoolman/database/models.py`, database models for `Project`, `Plate`, `PrintJob`, and `PrintJobSpool` are already fully defined:
  - `Project`: lines 121-129
  - `Plate`: lines 132-144
  - `PrintJob`: lines 147-159
  - `PrintJobSpool`: lines 162-171
- **API Models**: In `spoolman/api/v1/models.py`, there are no Pydantic representations for Project, Plate, or PrintJob.
- **API Router**: In `spoolman/api/v1/router.py`, there is no registration for the project, plate, or print_job routes.
- **Name Constraints**: In `tests_integration/tests/project/test_crud.py`, the project CRUD tests verify that:
  - Name is between 1 and 256 characters (lines 76-91): empty names and > 256 character names must fail with a status code of 400 or 422.
  - Deleting a project returns `200` or `204` (line 70).
  - Listing projects includes the `x-total-count` header (line 47).
- **Plate Boundaries**: In `tests_integration/tests/plate/test_boundaries.py`:
  - An invalid `project_id` must fail with 400, 404, or 422 (lines 9-18).
  - Negative inputs for `estimated_weight` and `estimated_time` must fail with 400 or 422 (lines 21-43).
  - Deleting a project fails with 400 or 409 if it has associated plates (lines 46-68).
- **Print Job Boundaries**: In `tests_integration/tests/print_job/test_boundaries.py`:
  - An invalid `plate_id` must fail with 400, 404, or 422 (lines 9-18).
  - An invalid `spool_id` in `spool_usages` must fail with 400, 404, or 422 (lines 21-36).
  - Negative spool usage weight must fail with 400 or 422 (lines 39-66).
  - Deleting a plate fails with 400 or 409 if it has associated print jobs (lines 74-97).
  - Chronological time validation: `end_time` before `start_time` must fail with 400 or 422 (lines 99-110).

## 2. Logic Chain

1. **Schema Definition**: Based on the observed test cases, the Pydantic models for Project, Plate, and PrintJob in `spoolman/api/v1/models.py` must support the following:
   - `Project`: fields `id`, `registered` (as `SpoolmanDateTime`), `name` (with string length constraint `1 <= length <= 256`), `description` (optional), and `link` (optional).
   - `Plate`: fields `id`, `registered`, `project_id`, `project` (optional nested model), `name` (length `1 <= length <= 256`), `file_path`, `estimated_weight` (non-negative float), `estimated_time` (non-negative integer), and `comment`.
   - `PrintJobSpool`: fields `spool_id` and `weight_used` (non-negative float).
   - `PrintJob`: fields `id`, `registered`, `plate_id`, `plate` (optional nested model), `status`, `start_time`, `end_time`, `printer_name`, `comment`, and `spool_usages` (list of `PrintJobSpool`).
2. **Database Helpers**:
   - Creating a plate requires fetching the parent project via `project.get_by_id(db, project_id)`. If the project does not exist, `ItemNotFoundError` is thrown, propagating a 404 response.
   - Creating/updating a print job requires fetching the parent plate via `plate.get_by_id(db, plate_id)` and each spool via `spool.get_by_id(db, spool_id)` (under `spool_usages`).
   - Updating `spool_usages` on a print job requires explicitly deleting existing `PrintJobSpool` records first to prevent SQLite IntegrityError, since `print_job_id` is a primary/foreign key constraint.
   - Chronological validation must compare naive UTC datetimes during creation and updates in the database helper (as well as Pydantic model validators).
3. **Delete Restrictions**:
   - In SQLAlchemy, deleting a parent entity when a child refers to it via a non-nullable foreign key raises `sqlalchemy.exc.IntegrityError` if foreign key constraints are active.
   - By catching `IntegrityError` inside the delete helpers and raising `ItemDeleteError` (mapped to `400` status code inside the routers), we satisfy the requirement that deleting a project fails with 400/409 if it has plates, and deleting a plate fails with 400/409 if it has print jobs.

## 3. Caveats

- **Weight Deduction (IMP-2)**: The actual remaining weight deduction is out-of-scope for IMP-1, but the spool usages relations and CRUD endpoints are fully supported to enable seamless integration with IMP-2.
- **SQLite vs. Other DBs**: The local setup runs on SQLite, but the database helpers use SQLAlchemy ORM expressions that are fully compatible with Postgres, MySQL, and CockroachDB.

## 4. Conclusion

Milestone IMP-1 requires:
1. Merging the Pydantic schemas in `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_models.py` into `spoolman/api/v1/models.py`.
2. Creating the DB helper files:
   - `spoolman/database/project.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_project_db.py`)
   - `spoolman/database/plate.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_plate_db.py`)
   - `spoolman/database/print_job.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_print_job_db.py`)
3. Creating the API router files:
   - `spoolman/api/v1/project.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_project_api.py`)
   - `spoolman/api/v1/plate.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_plate_api.py`)
   - `spoolman/api/v1/print_job.py` (copy from `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_print_job_api.py`)
4. Registering the routers in `spoolman/api/v1/router.py` (refer to `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_3/proposed_router.py`).

## 5. Verification Method

- Run the integration tests:
  ```bash
  python tests_integration/run.py sqlite
  ```
  The tests in `tests_integration/tests/project/`, `tests_integration/tests/plate/`, and `tests_integration/tests/print_job/` (excluding the weight deduction tier 4 tests) should pass with exit code 0.
- Verify files are placed in their correct layout positions and registered correctly.
