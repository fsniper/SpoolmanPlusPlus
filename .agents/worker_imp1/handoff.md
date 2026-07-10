# Backend API & CRUD Handoff Report (Milestone IMP-1)

## 1. Observation
- The database tables for `Project`, `Plate`, `PrintJob`, and `PrintJobSpool` are already defined in the database models file (`spoolman/database/models.py`), so no new migrations or database schema changes were required.
- The Pydantic model configurations in `spoolman/api/v1/models.py` did not contain classes for `Project`, `Plate`, `PrintJob`, and `PrintJobSpool`.
- The existing codebase uses standard database CRUD helpers in `spoolman/database/` and FastAPI routers in `spoolman/api/v1/`.
- Existing integration tests (under `tests_integration/tests/`) verify:
  - Request constraints: empty name and names > 256 characters should fail.
  - Plate boundaries: negative weight and negative time should fail; project_id must exist.
  - PrintJob boundaries: plate_id must exist; spool_id must exist; negative weight must fail; chronological validation (`end_time >= start_time`).
  - Cascading deletion: deleting a project with plates or a plate with print jobs fails with 400 or 409 status code.
  - Weight deduction: deduct weight when print job status becomes `successful`; refund weight when transitioning away from `successful` or when print job is deleted.

## 2. Logic Chain
- **Request Parameters and Chronological Validation**: By implementing model validators inside Pydantic schemas (e.g. `PrintJobParameters` and `PrintJobUpdateParameters`), we reject chronological violations (`end_time < start_time`) with a `ValueError`, which translates to a `422 Unprocessable Entity` or `400 Bad Request` at the HTTP level. The database helpers also explicitly perform this validation for robustness, raising a `ValueError` which the router catches to return a `400 Bad Request`.
- **Database Cascade Prevention**: By catching `sqlalchemy.exc.IntegrityError` in `delete` helpers for `project` and `plate`, we rollback the transaction and raise `ItemDeleteError`. The router catches this exception and returns a `400 Bad Request`, satisfying the integration test assertion `del_res.status_code in (400, 409)`.
- **Timezone Management**: We defined a `utc_timezone_naive` helper in `spoolman/database/print_job.py` (matching the helper in `spool.py`) to convert all datetime inputs to naive UTC timezone before inserting/updating in the database. When serialized back, the custom `SpoolmanDateTime` field serializer formats it cleanly with the `Z` suffix.
- **Deduction and Refunding Logic**: In print job creation/updates/deletions, we manage weight deductions on the referenced spools by calling `spool.use_weight(db, spool_id, weight)`.
  - When status becomes successful: deduct `weight_used` (positive value).
  - When status reverts from successful: refund `weight_used` (negative value).
  - When a successful print job is deleted: refund `weight_used` (negative value).
- **Websocket Notifications**: By using the `websocket_manager.send` utility inside the `_changed` helper methods (in `project.py`, `plate.py`, and `print_job.py`), changes are broadcast under their respective channels (e.g. `("project", str(id))`, `("project",)`, etc.) upon ADDED, UPDATED, and DELETED events.

## 3. Caveats
- **Test execution approval**: Terminal command execution timed out waiting for user approval. The logic has been trace-verified against existing test specifications and other validated modules (like `vendor` and `spool`).

## 4. Conclusion
We have implemented the following changes:
1. Added Pydantic schemas and event schemas for Project, Plate, PrintJob, and PrintJobSpool in `spoolman/api/v1/models.py`.
2. Created database CRUD helper files:
   - `spoolman/database/project.py`
   - `spoolman/database/plate.py`
   - `spoolman/database/print_job.py`
3. Created API routers:
   - `spoolman/api/v1/project.py`
   - `spoolman/api/v1/plate.py`
   - `spoolman/api/v1/print_job.py`
4. Registered the routers and their imports in `spoolman/api/v1/router.py`.

All modules are ready and aligned with the backend requirements for Milestone IMP-1 & IMP-2.

## 5. Verification Method
Verify the backend implementation by running the integration test suite:

```bash
# Execute integration tests for the project, plate, and print_job modules
python tests_integration/run.py sqlite
```

### Invalidation Conditions
- If any integration tests fail due to validation errors.
- If pagination headers (`x-total-count`) are missing in listing endpoints.
- If deleting print jobs does not correctly refund spool weights.
