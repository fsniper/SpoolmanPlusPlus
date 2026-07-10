## 2026-07-10T20:12:00Z
You are the Worker for Milestone 2.
Your working directory is /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_m2/.
Your task is to implement the Spoolman Backend API and CRUD for the Printer entity, integrate it with PrintJob, and write integration tests.

Please read:
- PROJECT.md at root (/Users/yalazi/Documents/PROJECTS/software/Spoolman/PROJECT.md)
- SCOPE.md at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_m2_gen2/SCOPE.md
- Synthesis of explorer findings at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/sub_orch_m2_gen2/synthesis.md
- Explorer 2 handoff at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_m2_2/handoff.md
- Explorer 3 handoff at /Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/explorer_m2_3/handoff.md

Implementation Tasks:
1. Define Pydantic models for `Printer` in `spoolman/api/v1/models.py`, including `Printer`, `PrinterParameters`, `PrinterUpdateParameters`, and `PrinterEvent`.
2. Create database CRUD helper routines in `spoolman/database/printer.py` supporting `create`, `update`, `get_by_id`, `find`, and `delete`. Ensure search logic for printer fields (name, model, location, comment) is implemented.
3. Trigger WebSocket notification events on printer mutations (creation, update, deletion) using `websocket_manager.send`.
4. Create REST API router in `spoolman/api/v1/printer.py` supporting GET, POST, PATCH, DELETE, and WebSocket updates (both for all printers and for a specific printer).
5. Register the `printer` router in `spoolman/api/v1/router.py`.
6. Integrate `printer` relationship into `PrintJob` CRUD and schemas so print job GET/POST/PATCH operations return `printer_id` and optional `printer` details.
7. Write comprehensive backend integration tests in `tests_integration/` to verify CRUD operations, WebSocket events, and relationship to Print Jobs.
8. Ensure all pytest tests pass successfully.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please execute the changes, run the builds and tests (e.g. `pytest` or `python tests_integration/run.py sqlite` or similar), verify layout compliance, write a handoff report to `/Users/yalazi/Documents/PROJECTS/software/Spoolman/.agents/worker_m2/handoff.md` and send a message to parent ID e4f162d3-d212-47a7-a311-13bffc9a5247 when done.
