# Project: Spoolman Printer Management

## Architecture
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic, WebSockets.
- Frontend: React, Refine, Vite, Ant Design, TypeScript.
- New entity `Printer` added to DB, REST API, Websockets, and Refine UI.
- `PrintJob` references `Printer` via `printer_id` foreign key.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Database Model & Alembic Migration | SQLAlchemy models and Alembic migration to add printer table and link it to print_job. Migrates printer_name to printer. | none | DONE |
| 2 | M2: Backend API and CRUD | Pydantic models, database CRUD helpers, FastAPI REST routers with WebSocket notifications, and integration tests. | M1 | IN_PROGRESS |
| 3 | M3: Frontend Refine UI (Printers) | Refine/AntD views for Printer list, create, edit. App.tsx resource registration. | M2 | PLANNED |
| 4 | M4: Frontend Print Job Integration | Update Print Job list/create/edit views to reference Printer via searchable select. | M3 | PLANNED |
| 5 | M5: E2E and Final Verification | Verify E2E functionality, run full backend test suite, and ensure frontend compilation. | M4 | PLANNED |

## Code Layout
- SQLAlchemy Models: `spoolman/database/models.py`
- Alembic Migrations: `migrations/versions/`
- Pydantic Models: `spoolman/api/v1/models.py`
- Database CRUD: `spoolman/database/printer.py`
- REST API router: `spoolman/api/v1/printer.py`
- Registered Routers: `spoolman/api/v1/router.py`
- Frontend Pages: `client/src/pages/printers/`
- Frontend Main App: `client/src/App.tsx`
- Integration Tests: `tests_integration/`

## Interface Contracts
### Printer REST API
- `GET /api/v1/printer` - Search/list printers
- `POST /api/v1/printer` - Create printer
- `GET /api/v1/printer/{id}` - Get printer by ID
- `PATCH /api/v1/printer/{id}` - Update printer details
- `DELETE /api/v1/printer/{id}` - Delete printer
- `WEBSOCKET /api/v1/printer` - Stream printer events
- `WEBSOCKET /api/v1/printer/{id}` - Stream printer events for a specific printer
