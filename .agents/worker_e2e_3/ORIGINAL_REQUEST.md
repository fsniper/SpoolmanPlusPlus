## 2026-07-08T22:22:52Z
You are a teamwork_preview_worker. Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_e2e_3.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task:
1. Initialize your BRIEFING.md and progress.md in your working directory.
2. Read the reviewer's feedback at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/reviewer_e2e_2/handoff.md.
3. Clean up the incorrect test files from the root of tests_integration/tests/ by deleting them:
   - tests_integration/tests/test_project_crud.py
   - tests_integration/tests/test_plate_crud.py
   - tests_integration/tests/test_print_job_crud.py
   - tests_integration/tests/test_boundaries.py
   - tests_integration/tests/test_workflow.py
   - tests_integration/tests/test_weight_deduction.py
4. Create the proper directory structure and implement the integration tests inside the subdirectories:
   - tests_integration/tests/project/
     - __init__.py
     - test_crud.py: Project CRUD + project boundary validations (empty name, name too long). Remove unused imports (no unused pytest or assert_dicts_compatible).
   - tests_integration/tests/plate/
     - __init__.py
     - test_crud.py: Plate CRUD under a project. Remove unused imports.
     - test_boundaries.py: Plate relationship/boundary validations (invalid project ID, negative weight/time) and cascade delete block/conflict validation (deleting a project with plates). In finally blocks, ensure that deletions catch and ignore any HTTPError (so they don't mask assertion failures if a deletion already occurred or failed).
   - tests_integration/tests/print_job/
     - __init__.py
     - test_crud.py: Print job CRUD. Remove unused imports.
     - test_boundaries.py: Print job relationship validations (invalid plate ID, invalid spool ID, negative spool usage weight) and delete block/conflict validation (deleting a plate with print jobs). Also add start/end time chronological validation (e.g. end_time before start_time should fail). Use try-except to ignore HTTPErrors in teardown cleanups.
     - test_workflow.py: The integrated printing workflow. Use try-except to ignore HTTPErrors in teardown cleanups.
     - test_weight_deduction.py: The weight deduction business logic (successful status deduction, creation deduction, multi-spool deduction, idempotency, clamping). Use try-except to ignore HTTPErrors in teardown cleanups.
5. Propose the command `python tests_integration/run.py sqlite` to build and run the tests. Make sure you wait for the command to finish. Verify that the suite runs, and the new tests fail with 404/405 (since backend routes are not registered yet).
6. Document your changes and the test run findings in a handoff.md report.
7. Send a message to your parent (Conversation ID: 5bec82bd-5819-4319-9ca5-8fd6d0ffd2f3) when done.
