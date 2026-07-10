# Scope: Milestone 2 — Backend API and CRUD

## Architecture
This milestone introduces the `Printer` entity into the Spoolman backend and integrates it with existing models, specifically the `PrintJob` model.
- **Pydantic Models**: Define Pydantic schemas in `spoolman/api/v1/models.py`.
- **Database CRUD**: Implement CRUD methods in `spoolman/database/printer.py`.
- **WebSocket Notifications**: Trigger WebSockets on mutate operations using `websocket_manager.send`.
- **REST API Router**: Implement GET, POST, PATCH, DELETE and WS endpoints in `spoolman/api/v1/printer.py`.
- **Registration**: Register the router in `spoolman/api/v1/router.py`.
- **PrintJob Relationship**: Update schemas and CRUD for `PrintJob` to link to `Printer`.
- **Integration Tests**: Verify end-to-end functionality via pytest integration tests.

## Work Items
| Req | Name | Scope | Status |
|-----|------|-------|--------|
| 1 | Pydantic Models | Define models for Printer, PrinterParameters, PrinterUpdateParameters, PrinterEvent in `spoolman/api/v1/models.py` | IN_PROGRESS |
| 2 | DB CRUD helper routines | Implement create, update, get_by_id, find, and delete supporting printer field search in `spoolman/database/printer.py` | IN_PROGRESS |
| 3 | WebSocket notifications | Trigger WebSocket events on mutation via `websocket_manager.send` | IN_PROGRESS |
| 4 | REST API Router | Create GET/POST/PATCH/DELETE/WS endpoints in `spoolman/api/v1/printer.py` | IN_PROGRESS |
| 5 | Register API Router | Add the printer router to `spoolman/api/v1/router.py` | IN_PROGRESS |
| 6 | PrintJob integration | Update PrintJob schema & CRUD to return `printer_id` and optional `printer` details | IN_PROGRESS |
| 7 | Integration Tests | Add tests in `tests_integration/` verifying CRUD, WebSocket events, and PrintJob relation | IN_PROGRESS |
| 8 | Build and Tests | Ensure all pytest tests pass | IN_PROGRESS |

## Interface Contracts
### Pydantic Models for Printer
- `PrinterParameters`: Name, model, location, comment, etc.
- `Printer`: Database fields including `id`, `name`, `model`, `location`, `comment`, and system timestamps/relationships.
- `PrinterUpdateParameters`: Optional fields for PATCH update.
- `PrinterEvent`: Event payload for WebSocket updates.

### CRUD helper signatures
- `create(db: Session, printer: PrinterParameters) -> Printer`
- `update(db: Session, printer_id: int, printer: PrinterUpdateParameters) -> Printer`
- `get_by_id(db: Session, printer_id: int) -> Printer`
- `find(db: Session, ...) -> list[Printer]`
- `delete(db: Session, printer_id: int) -> None`
