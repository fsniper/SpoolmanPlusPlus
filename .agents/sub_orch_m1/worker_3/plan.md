# Task Execution Plan - Database Worker 3

This plan details the step-by-step changes to resolve:
1. Issue A & B: Shared Printer Renaming / Duplication.
2. Issue C: SQLite Downgrade Failure.
3. Verification of changes via integration tests.

## Steps

### 1. Modify `spoolman/database/models.py`
- Remove the `@printer_name.setter` property entirely from the `PrintJob` class.
- Retain only the `@property` getter for `printer_name`.
- **Verification**: Code compiles, and `PrintJob` no longer accepts `printer_name` assignment directly.

### 2. Modify `spoolman/database/print_job.py`
- Update the `create` function to check if `printer_name` is provided. If so, query the database for a `Printer` with that name. If it exists, link it as `printer=db_printer`. If it does not exist, instantiate a new `Printer`, add it to the database session, flush, and then set `printer=db_printer`.
- Update the `update` function to intercept `printer_name` in the incoming data. If provided, query for an existing `Printer` with that name. If it exists, link it. If not, create a new `Printer` with that name, add it to the session, flush, and link it. If `printer_name` is explicitly set to None or an empty string, set the print job's `printer` relationship to None.
- **Verification**: The print job service methods handle printer lookups properly and do not rename existing printers or create duplicates.

### 3. Modify the migration script
- Modify `migrations/versions/2026_07_10_1614-c0e86b24d77b_add_printer_table.py`'s `downgrade` function.
- Add a check for `bind.dialect.name != 'sqlite'` before calling `batch_op.drop_constraint`.
- **Verification**: SQLite downgrade command runs successfully without metadata errors.

### 4. Adjust verification test script (if necessary)
- Check `tests_integration/test_challenger_db.py` to ensure it doesn't fail due to model setter deletion, or adapt its test cases to use the service layer (or clean them up if they are obsolete/broken).

### 5. Run Tests
- Run `poetry run poe itest` or similar test execution method to ensure all integration tests pass.
- Document test results.
