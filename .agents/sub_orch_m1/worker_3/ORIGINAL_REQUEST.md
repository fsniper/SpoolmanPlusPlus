## 2026-07-10T15:57:47Z
You are Database Worker 3. Your working directory is: /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_m1/worker_3/.

Your mission is to implement fixes for the issues identified in Iteration 1:
1. **Issue A & B (Shared Printer Renaming / Duplication)**:
   - In `spoolman/database/models.py`, modify the `PrintJob` model to **remove** the `@printer_name.setter` property entirely. Only keep the `@property` getter:
     ```python
     @property
     def printer_name(self) -> str | None:
         return self.printer.name if self.printer else None
     ```
   - In `spoolman/database/print_job.py`, move the printer lookup and creation logic into the database service layer:
     * In the `create` function, check if `printer_name` is provided. If so, query for an existing `Printer` with that name. If it exists, use it; otherwise, instantiate a new `Printer` with that name, add it to the session, flush, and link it as `printer=db_printer`.
     * In the `update` function, intercept `printer_name` in the incoming data. If provided, query for an existing `Printer` with that name. If it exists, use it; otherwise, create a new `Printer` with that name, add/flush, and set `print_job.printer = db_printer`. If `printer_name` is explicitly updated to None or an empty string, set `print_job.printer = None`.
2. **Issue C (SQLite Downgrade Failure)**:
   - In the migration script `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py`, modify the `downgrade` function to dynamically check the dialect name before attempting to drop the foreign key constraint. In SQLite, the batch alter operation recreate-and-copy process handles constraint drops automatically when columns are dropped, and calling `drop_constraint` by name can fail due to missing reflected constraint names in default SQLite metadata.
   - Implement the dialect check inside the batch alter block:
     ```python
     with op.batch_alter_table("print_job", schema=None) as batch_op:
         if bind.dialect.name != 'sqlite':
             batch_op.drop_constraint('fk_print_job_printer_id', type_='foreignkey')
         batch_op.drop_column('printer_id')
     ```
3. **Verify and Run Tests**:
   - Run the integration tests using the command `poetry run poe itest` (or `python tests_integration/run.py` or run `pytest` directly on `tests_integration/tests/`).
   - Ensure all backend integration tests pass.
   - Document the test command used, the databases tested, and the test results in your handoff report.

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.

Write a detailed handoff.md in your working directory outlining the changes made and the test execution outcomes. When done, notify the parent orchestrator (conversation ID e4f162d3-d212-47a7-a311-13bffc9a5247).
