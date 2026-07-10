## 2026-07-10T16:12:33Z
You are the Database Worker. Your working directory is: /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_m1/worker_1/.
Your mission is to implement the database model changes and Alembic migration for Milestone 1.

Follow these instructions carefully:
1. Modify `spoolman/database/models.py` to:
   - Add the `Printer` model:
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
   - In `PrintJob` class:
     * Remove the `printer_name` column (`printer_name: Mapped[str | None] = mapped_column(String(256))`).
     * Add `printer_id` column: `printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"))`.
     * Add `printer` relationship: `printer: Mapped[Optional["Printer"]] = relationship(back_populates="print_jobs")`.
     * Add a python `@property` and setter for `printer_name` to preserve compatibility with existing API/CRUD code:
       ```python
       @property
       def printer_name(self) -> str | None:
           return self.printer.name if self.printer else None

       @printer_name.setter
       def printer_name(self, value: str | None) -> None:
           if value is None or value == "":
               self.printer = None
           else:
               if self.printer is not None:
                   self.printer.name = value
               else:
                   self.printer = Printer(name=value)
       ```
2. Generate and customize the Alembic migration script:
   - Run the alembic revision generator to create the migration file template.
   - Customize the generated script's `upgrade()` and `downgrade()` functions to:
     * Create the `printer` table.
     * Add `printer_id` column to `print_job` referencing `printer.id`.
     * Select unique, non-empty `printer_name` values from the existing `print_job` table.
     * For each unique name, insert a corresponding row in the `printer` table (with `registered` set to current time, and other attributes null).
     * Update `print_job` to set `printer_id` to the ID of the newly inserted printer record where `printer_name` matches.
     * Drop the `printer_name` column from the `print_job` table.
     * In `downgrade()`, perform the inverse: add `printer_name` column back to `print_job`, restore data from `printer` table matching `printer_id`, drop `printer_id` column, and drop `printer` table.
     * Ensure the migration uses `op.batch_alter_table("print_job")` for SQLite compatibility and works on SQLite, PostgreSQL, and MySQL.

3. Verify migration:
   - Run standard build and test validation commands.
   - Specifically run the integration test runner: `poetry run poe itest` (or `python tests_integration/run.py` or just `pytest` depending on the environment setup) to verify that the application builds, migrations apply, and all backend integration tests pass.
   - Document the test command used and the output results in your handoff.md.

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.

Write a detailed handoff.md in your working directory outlining:
- The exact changes made to `models.py`.
- The filename and path of the created Alembic migration script.
- The command used to run tests, and the test results (e.g., exit codes, passing tests count).
When done, notify the parent orchestrator (conversation ID e4f162d3-d212-47a7-a311-13bffc9a5247).
