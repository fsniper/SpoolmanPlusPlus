## 2026-07-08T22:16:14Z
You are a teamwork_preview_explorer. Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_e2e_1.
Your task is to design the integration test cases for the new 3D Print Management feature (Projects, Plates, and Print Jobs) in Spoolman, covering Tiers 1-4.
Please:
1. Initialize your BRIEFING.md and progress.md in your working directory.
2. Read the existing integration tests under tests_integration/tests/ (e.g. in tests_integration/tests/spool/, tests_integration/tests/conftest.py, etc.) to understand the project structure, imports, helpers, fixtures, and how tests are structured.
3. Read the database migration file migrations/versions/2026_07_08_2312-fdc4cb99d052_add_print_management.py to understand the DB schema.
4. Design detailed integration test specifications covering:
   - CRUD operations (POST, GET, PATCH, DELETE, list) for Projects, Plates, and Print Jobs.
   - Relationships and foreign key validation (e.g. creating a Plate with non-existent project_id should fail, creating a Print Job with non-existent plate_id or spool_id should fail).
   - The business logic rule: setting a Print Job's status to "successful" must automatically deduct the print_job_spool weight_used from the linked Spool's remaining_weight.
5. Save your final design/report as handoff.md in your working directory.
6. Send a message to your parent (Conversation ID: 5bec82bd-5819-4319-9ca5-8fd6d0ffd2f3) when you are done.
