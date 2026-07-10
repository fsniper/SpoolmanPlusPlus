# Original User Request

## Follow-up — 2026-07-10T15:08:21Z

Build out a full-stack Printer Management feature in Spoolman, including a database table, REST API endpoints, Refine frontend list/create/edit views, and integrate it into the Print Jobs entity so that print jobs reference a specific Printer instead of a text field.

Working directory: /Users/yalazi/Documents/PROJECTS/software/Spoolman
Integrity mode: demo

## Requirements

### R1. Database Model & Migration
Create a database table `printer` containing `id`, `registered`, `name` (required, non-empty), `model`, `location`, and `comment`. Add a `printer_id` foreign key pointing to `printer.id` on the `print_job` table. Create an Alembic migration that sets up these tables, extracts unique values from existing print jobs' `printer_name` column to populate the `printer` table, links the print jobs to the corresponding new printers, and retires the old `printer_name` column.

### R2. FastAPI Backend CRUD
Implement Python CRUD operations and REST API endpoints (with WebSocket notifications on creation/update/deletion) for the `Printer` entity, following the existing patterns in the backend code.

### R3. Printer Management Frontend UI
Create Refine and Ant Design views in the React frontend for listing, creating, and editing Printers. Add the Printer resource with a suitable navigation icon to the App.tsx file.

### R4. Print Job Form & UI Integration
Update the Print Job listing and create/edit forms. The printer field in the Print Job form should be a searchable select dropdown populated from the Printer API, setting `printer_id`.

## Acceptance Criteria

### Database & Migration
- [ ] Alembic migration applies successfully and migrates existing `printer_name` records to `printer` records.
- [ ] Database schema validation succeeds and all SQLAlchemy model relationships function properly.

### Backend Functionality & Testing
- [ ] Printer REST API endpoints (GET, POST, PATCH, DELETE) function correctly and trigger WebSocket updates.
- [ ] Integration tests verify the CRUD operations for Printers and their relations to Print Jobs.

### Frontend Quality & Compilation
- [ ] React frontend builds successfully without TypeScript or build errors (`npm run build`).
- [ ] Printer resource is accessible in the navigation sidebar.
- [ ] Print Job forms use a searchable Select dropdown for selecting a Printer.
