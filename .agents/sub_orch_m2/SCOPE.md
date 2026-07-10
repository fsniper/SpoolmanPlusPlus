# Scope: Milestone 2: Backend API and CRUD

## Architecture
Milestone 2 adds backend API and database CRUD support for `Printer` objects and integrates it with `PrintJob` objects:
- **Pydantic Schemas**: Defined in `spoolman/api/v1/models.py` (`Printer`, `PrinterParameters`, `PrinterUpdateParameters`, `PrinterEvent`).
- **Database CRUD**: Defined in `spoolman/database/printer.py` (`create`, `update`, `get_by_id`, `find`, `delete`).
- **REST API Routing**: Defined in `spoolman/api/v1/printer.py` supporting standard GET/POST/PATCH/DELETE endpoints, and WebSocket updates (on `/printer` and `/printer/{printer_id}`).
- **Router Registration**: Register the `/printer` router in `spoolman/api/v1/router.py`.
- **PrintJob Integration**: Update `PrintJob` creation/update to accept `printer_id`, update Pydantic models to return `printer_id` and optional `printer` details.
- **Integration Verification**: Backend integration tests under `tests_integration/`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Pydantic Models | Define `Printer` models in `spoolman/api/v1/models.py` | None | PLANNED |
| 2 | Database CRUD | Implement CRUD operations in `spoolman/database/printer.py` | M1 | PLANNED |
| 3 | API Router | Create `spoolman/api/v1/printer.py` & register in `router.py` | M2 | PLANNED |
| 4 | PrintJob Integration | Update print job models and database code to link `Printer` | M3 | PLANNED |
| 5 | Integration Tests | Add tests in `tests_integration/` and verify all tests pass | M4 | PLANNED |

## Interface Contracts
### Pydantic Models
- `Printer`:
  - `id`: int
  - `registered`: SpoolmanDateTime
  - `name`: str
  - `model`: str \| None
  - `location`: str \| None
  - `comment`: str \| None
- `PrinterParameters`:
  - `name`: str
  - `model`: str \| None
  - `location`: str \| None
  - `comment`: str \| None
- `PrinterUpdateParameters`:
  - Same as parameters but name is optional (`str | None`)
- `PrinterEvent`:
  - Inherits `Event`, resource is `"printer"`, payload is `Printer`.
