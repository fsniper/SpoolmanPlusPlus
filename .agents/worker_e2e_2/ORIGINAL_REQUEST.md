## 2026-07-08T22:18:29Z
You are a teamwork_preview_worker. Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_e2e_2.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task:
1. Initialize your BRIEFING.md and progress.md in your working directory.
2. Read the test design report from the Explorer at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_e2e_1/handoff.md.
3. Modify/write integration test files only. You must edit:
   - tests_integration/tests/conftest.py (to add fixtures: random_project, random_plate, random_print_job and their implementation context managers).
   - Create directories and files under tests_integration/tests/ to test:
     - Project CRUD (test_project_crud.py or tests_integration/tests/project/test_crud.py)
     - Plate CRUD (test_plate_crud.py or tests_integration/tests/plate/test_crud.py)
     - Print Job CRUD (test_print_job_crud.py or tests_integration/tests/print_job/test_crud.py)
     - Boundary validations and foreign key validation (test_boundaries.py)
     - Multi-entity workflows (test_workflow.py)
     - Spool weight deduction business logic (test_weight_deduction.py or tests_integration/tests/print_job/test_weight_deduction.py)
   Ensure that the tests follow pytest conventions, use the URL fixture from conftest.py, handle resources cleanup (deletes) in teardowns, and assert the expected status codes, JSON formats, and behaviors.
4. Build the test environment and run the tests using:
   python tests_integration/run.py sqlite
   Verify that the test runner executes and that the new tests fail as expected (since backend is not implemented yet).
5. Document the changes made and the run results in a handoff.md report.
6. Send a message to your parent (Conversation ID: 5bec82bd-5819-4319-9ca5-8fd6d0ffd2f3) when done.
