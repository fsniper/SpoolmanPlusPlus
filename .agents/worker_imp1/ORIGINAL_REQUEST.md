## 2026-07-08T22:30:23Z
You are a versatile worker. Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_imp1.
Your mission is to implement Milestone IMP-1: Backend API & CRUD for Spoolman.
Refer to:
- PROJECT.md at /Users/yalazi/Documents/PROJECTS/software/Spoolman/PROJECT.md
- SCOPE.md at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_impl/SCOPE.md
- The design analysis report from Explorer 2 at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_imp1_2/handoff.md.

You must implement:
1. Addition of Project, Plate, PrintJob, and PrintJobSpool models and schemas to spoolman/api/v1/models.py.
2. Database helper CRUD operations:
   - spoolman/database/project.py
   - spoolman/database/plate.py
   - spoolman/database/print_job.py
3. API routers:
   - spoolman/api/v1/project.py
   - spoolman/api/v1/plate.py
   - spoolman/api/v1/print_job.py
4. Register these routers in spoolman/api/v1/router.py.

Guidelines:
- All request parameters should have constraints: name validation (min_length=1, max_length=256), non-negative estimates, etc.
- In print_job update/create/delete, implement status-based logic (e.g. check status to determine if weight deduction is needed, but note that the actual spool.use_weight updates and refunding logic is what connects this to Spoolman's core. Be sure to handle relationship mapping/CRUD for PrintJobSpool correctly).
- In database deletes: catch sqlalchemy.exc.IntegrityError when deleting a parent that has active children (e.g. deleting a project with plates, or a plate with print jobs), and raise a custom exception that the router catches to return 409 Conflict (or 400 as per tests).
- Ensure all list endpoints include pagination headers (x-total-count header and list response) and support sorting/filtering.
- Ensure websocket notifications are fired on resource changes (ADDED, UPDATED, DELETED) just like spool/filament/vendor.
- Ensure all datetimes are UTC timezone-naive when storing to DB, and serialized cleanly with Z suffix.
- Verify your changes by running the integration tests: python tests_integration/run.py sqlite and ensure the tests for projects, plates, and print_jobs pass successfully.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your report to /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_imp1/handoff.md and send a message back to me (conversation ID: 78bd8cc3-83c0-4fe9-9dca-12d02cbf2a3b).
