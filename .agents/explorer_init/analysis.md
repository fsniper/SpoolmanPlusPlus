# Spoolman Printer Management Exploration Analysis

This report outlines the codebase investigation findings for Spoolman, with the goal of designing and implementing a Printer Management feature.

---

## 1. Database Architecture, SQLAlchemy Models & Alembic Migrations

### SQLAlchemy Models
The backend SQLAlchemy model definitions are defined in `spoolman/database/models.py`.
- **Base Class**: The declarative base uses standard SQLAlchemy ORM setup:
  ```python
  class Base(AsyncAttrs, DeclarativeBase):
      pass
  ```
- **Existing Entities**: Tables include `vendor`, `filament`, `spool`, `setting`, `project`, `plate`, `print_job`, `print_job_spool`, and extra metadata fields (e.g., `vendor_field`, `filament_field`, `spool_field`).

### Database Session Setup
The database wrapper and connection lifecycle are defined in `spoolman/database/database.py`.
- **Engine Creation**: Standard asynchronous engine setup with support for SQLite, PostgreSQL, MariaDB, and MySQL via `create_async_engine`.
- **Session Yielding**: Dependency injection is handled by `get_db_session()`, yielding an `AsyncSession`:
  ```python
  async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
      if __db is None or __db.session_maker is None:
          raise RuntimeError("DB is not setup.")
      async with __db.session_maker() as session:
          try:
              yield session
              await session.commit()
          except Exception as exc:
              await session.rollback()
              raise exc
          finally:
              await session.close()
  ```

### Migrations
Spoolman uses **Alembic** to manage database schemas.
- **Configuration**: Root-level `alembic.ini` configuration pointing to the `migrations/` directory.
- **Migration Directory Structure**:
  - `migrations/env.py` manages execution contexts.
  - `migrations/versions/` contains versioned Python migration scripts.
- **Migration File Naming**: Named with timestamp prefixes and unique revision hashes, e.g., `2026_07_08_2312-fdc4cb99d052_add_print_management.py`.
- **Latest Migration**: The last migration `fdc4cb99d052` added Print Management tables (`project`, `plate`, `print_job`, and `print_job_spool`).

---

## 2. FastAPI Schemas, CRUD, Router & Real-Time Websocket Updates

### FastAPI Pydantic Schemas
FastAPI Pydantic request/response schemas are declared in `spoolman/api/v1/models.py`.
- Models subclass `pydantic.BaseModel`.
- Direct transformation from ORM is performed via a static helper method, e.g., `from_db(item: models.Entity) -> Entity`.

### CRUD Modules
Business logic and database interactions are isolated in `spoolman/database/{entity}.py` (e.g., `spoolman/database/print_job.py`).
- They export operations: `create`, `get_by_id`, `find`, `update`, and `delete`.
- Event hooks are called on modifications: e.g., `await print_job_changed(print_job, EventType.UPDATED)`.

### REST API Router Structure
API routing is structured under `spoolman/api/v1/`:
- Individual routers exist for each entity (e.g., `spoolman/api/v1/print_job.py`).
- All routers are registered in the main FastAPI application defined in `spoolman/api/v1/router.py` using `app.include_router(entity.router)`.

### Websocket Notification System
Websockets publish resource updates to clients using a publish-subscribe subscription tree.
- **Subscription Tree (`spoolman/ws.py`)**:
  `websocket_manager` tracks connected clients and categories:
  - **Root-level subscription `()`**: Serves client connection at `ws://<host>/api/v1/` to listen to all updates.
  - **Resource-level subscription `(resource_name,)`**: E.g., `("print_job",)` to receive updates on any print jobs. Served at `ws://<host>/api/v1/print_job`.
  - **Instance-level subscription `(resource_name, item_id)`**: E.g., `("print_job", "42")` to monitor a specific print job. Served at `ws://<host>/api/v1/print_job/{id}`.
- **Publishing Events**:
  Inside CRUD modules, once `db.commit()` succeeds, the helper posts events to `websocket_manager.send()` wrapping Pydantic entity representations in event models like `PrintJobEvent`.

---

## 3. React Refine Frontend Structure

### Directory Structure & Resource Registration
The frontend is built with **React, Vite, Refine, and Ant Design**.
- **Page Code**: Page components are organized by entity inside `client/src/pages/{entity_plural}/` (e.g., `client/src/pages/print_jobs/`).
- **Resource Configuration**: Resources are registered in `client/src/App.tsx` within `<Refine resources={[...]}>`:
  ```typescript
  {
    name: "print_job",
    list: "/print_job",
    create: "/print_job/create",
    edit: "/print_job/edit/:id",
    meta: {
      canDelete: true,
      icon: <PrinterOutlined />,
    },
  }
  ```
- **Route Handling**: Lazy loadable wrappers (`LoadableResourcePage`, `LoadablePrintJobPage`, etc.) map URL paths to physical component paths.

### Ant Design Usage & Live Update Hooks
- **Table Integration**: The `list.tsx` views utilize `@refinedev/antd`'s `useTable` hook and Ant Design's `<Table>` components.
- **Form Controls**: Edit/Create forms use `useForm` from `@refinedev/antd` mapping fields to `<Form.Item>` components.
- **Real-Time Client Updates**:
  The custom hook `useLiveify` (`client/src/components/liveify.ts`) integrates with Refine's `liveProvider` to subscribe to WebSockets for currently displayed item IDs. It listens to payload updates and updates table state dynamically without requiring page refreshes.

---

## 4. Current Structure of Print Jobs

### Backend Definition
- **SQLAlchemy model (`spoolman/database/models.py`)**:
  ```python
  class PrintJob(Base):
      __tablename__ = "print_job"
      id: Mapped[int] = mapped_column(primary_key=True, index=True)
      registered: Mapped[datetime] = mapped_column()
      plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"))
      plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
      status: Mapped[str] = mapped_column(String(64))  # e.g., queued, in_progress, successful, failed, canceled
      start_time: Mapped[datetime | None] = mapped_column()
      end_time: Mapped[datetime | None] = mapped_column()
      printer_name: Mapped[str | None] = mapped_column(String(256))  # Simple string input, not associated with a printer entity
      comment: Mapped[str | None] = mapped_column(String(1024))
      spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
  ```
- **Pydantic Schemas (`spoolman/api/v1/models.py`)**:
  - `PrintJob`: Maps directly to DB parameters.
  - `PrintJobSpool`: Tracks used spools and weights.
  - `PrintJobEvent`: Wrapper for real-time WebSocket payloads.
- **Router Endpoints (`spoolman/api/v1/print_job.py`)**:
  - `GET /print_job` - Search print jobs.
  - `WEBSOCKET /print_job` - Stream updates for all jobs.
  - `GET /print_job/{id}` - Fetch single print job.
  - `WEBSOCKET /print_job/{id}` - Stream updates for a specific job.
  - `POST /print_job` - Create job.
  - `PATCH /print_job/{id}` - Update job attributes.
  - `DELETE /print_job/{id}` - Delete job.

### Frontend Definition
- **TypeScript Model (`client/src/pages/print_jobs/model.tsx`)**:
  `IPrintJob` and `IPrintJobSpool` match the backend properties.
- **CRUD Operations**:
  - `list.tsx`: Displays a grid with color-coded status badges, printing times, and associated metadata.
  - `create.tsx` / `edit.tsx`: Uses `useSelect` to associate a plate and specify multiple spools and weights. The printer field is a standard text input element.

---

## 5. Proposed Printer Management Implementation Strategy

To add structured printer management while preserving the existing database and codebase conventions, follow this plan:

### Step 1: Database Model & Alembic Migration
1. Add `Printer` SQLAlchemy model to `spoolman/database/models.py`:
   ```python
   class Printer(Base):
       __tablename__ = "printer"
       id: Mapped[int] = mapped_column(primary_key=True, index=True)
       registered: Mapped[datetime] = mapped_column()
       name: Mapped[str] = mapped_column(String(256))
       model: Mapped[str | None] = mapped_column(String(256))
       comment: Mapped[str | None] = mapped_column(String(1024))
   ```
2. Link `Printer` to `PrintJob`:
   Add a nullable foreign key `printer_id` mapping to `printer.id` in the `PrintJob` model:
   ```python
   printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"))
   printer: Mapped[Optional["Printer"]] = relationship()
   ```
3. Generate and run a new Alembic migration:
   `alembic revision --autogenerate -m "add_printer_management"`

### Step 2: Backend API and CRUD
1. Define Pydantic models `Printer`, `PrinterParameters`, `PrinterUpdateParameters`, and `PrinterEvent` in `spoolman/api/v1/models.py`.
2. Add CRUD helper routines in `spoolman/database/printer.py` supporting `create`, `update`, `get_by_id`, `find`, and `delete`. Trigger `printer_changed` WebSocket events on mutations.
3. Write API router file `spoolman/api/v1/printer.py` containing GET, POST, PATCH, DELETE, and WebSocket routes.
4. Mount the new router inside `spoolman/api/v1/router.py`.

### Step 3: Frontend Client Changes
1. Create frontend pages under `client/src/pages/printers/`:
   - `model.tsx` defining `IPrinter`.
   - `list.tsx` for listing printers, utilizing `useLiveify` for real-time changes.
   - `create.tsx` and `edit.tsx` for managing printer properties.
2. Register the resource in `client/src/App.tsx`:
   Add a `printer` route, loading components via a loadable import helper, and configure the menu navigation. Recommended: Use the `PrinterOutlined` icon for printers, and choose another icon (e.g., `PlayCircleOutlined` or `BuildOutlined`) for print jobs.
3. Enhance `print_jobs/create.tsx` and `edit.tsx`:
   Replace the plain text input field for `printer_name` with a select dropdown populated via Refine's `useSelect` hook targetting the `printer` resource.
