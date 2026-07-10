# Original User Request

## Initial Request — 2026-07-10T20:10:04Z

Manage and execute Milestone 2: Backend API and CRUD.

Requirements:
1. Define Pydantic models for `Printer` in `spoolman/api/v1/models.py`, including `Printer`, `PrinterParameters`, `PrinterUpdateParameters`, and `PrinterEvent`.
2. Create database CRUD helper routines in `spoolman/database/printer.py` supporting `create`, `update`, `get_by_id`, `find`, and `delete`. Ensure search logic for printer fields (name, model, location, comment) is implemented.
3. Trigger WebSocket notification events on printer mutations (creation, update, deletion) using `websocket_manager.send`.
4. Create REST API router in `spoolman/api/v1/printer.py` supporting GET, POST, PATCH, DELETE, and WebSocket updates (both for all printers and for a specific printer).
5. Register the `printer` router in `spoolman/api/v1/router.py`.
6. Integrate `printer` relationship into `PrintJob` CRUD and schemas so print job GET/POST/PATCH operations return `printer_id` and optional `printer` details.
7. Write comprehensive backend integration tests in `tests_integration/` to verify CRUD operations, WebSocket events, and relationship to Print Jobs.
8. Ensure all pytest tests pass successfully.

Please initialize your `SCOPE.md` in your working directory, run the iteration loop (Explorer -> Worker -> Reviewer -> Challenger -> Auditor), and when completed, write a handoff.md in your working directory and notify the parent orchestrator.
