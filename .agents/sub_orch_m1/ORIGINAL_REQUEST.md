# Original User Request

## Initial Request — 2026-07-10T15:10:33Z

You are the Sub-Orchestrator for Milestone 1: Database Model & Alembic Migration.
Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_m1/.
Your parent conversation ID is e4f162d3-d212-47a7-a311-13bffc9a5247. Please send all status updates and completion messages to this parent ID.

Mission:
Manage and execute Milestone 1: Database Model & Alembic Migration.

Requirements:
1. Add SQLAlchemy model `Printer` to `spoolman/database/models.py` with: `id`, `registered` (datetime), `name` (string, required, non-empty), `model` (string, nullable), `location` (string, nullable), and `comment` (string, nullable).
2. Add `printer_id` foreign key column (referencing `printer.id`) and `printer` relationship (relationship to `Printer`, nullable) on `PrintJob` in `spoolman/database/models.py`.
3. Create and customize an Alembic migration script. The migration must:
   - Create the `printer` table.
   - Add `printer_id` column to `print_job` referencing `printer.id`.
   - Select unique, non-empty `printer_name` values from the existing `print_job` table.
   - For each unique name, insert a corresponding row in the `printer` table (with `registered` set to current time, and other attributes null).
   - Update `print_job` to set `printer_id` to the ID of the newly inserted printer record where `printer_name` matches.
   - Drop the `printer_name` column from the `print_job` table.
4. Verify migration applies and database schema validation passes.
5. All backend tests must build and pass successfully.

Please initialize your `SCOPE.md` in your working directory, run the iteration loop (Explorer -> Worker -> Reviewer -> Challenger -> Auditor), and when completed, write a handoff.md in your working directory and notify the parent orchestrator.
