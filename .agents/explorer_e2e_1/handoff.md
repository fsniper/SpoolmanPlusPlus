# Handoff Report - 3D Print Management Integration Test Suite Design

This report specifies the design of the integration test suite for the new 3D Print Management feature (Projects, Plates, and Print Jobs) in Spoolman, covering Tiers 1-4.

---

## 1. Observation

Direct observations from the codebase:

1. **Database Migration Schema (`migrations/versions/2026_07_08_2312-fdc4cb99d052_add_print_management.py`)**:
   - `project`: Table with columns `id` (Integer, PK), `registered` (DateTime, non-nullable), `name` (String(256), non-nullable), `description` (String(1024), nullable), and `link` (String(1024), nullable).
   - `plate`: Table with columns `id` (Integer, PK), `registered` (DateTime, non-nullable), `project_id` (Integer, FK to `project.id`, non-nullable), `name` (String(256), non-nullable), `file_path` (String(1024), nullable), `estimated_weight` (Float, nullable), `estimated_time` (Integer, nullable, in seconds), and `comment` (String(1024), nullable).
   - `print_job`: Table with columns `id` (Integer, PK), `registered` (DateTime, non-nullable), `plate_id` (Integer, FK to `plate.id`, non-nullable), `status` (String(64), non-nullable), `start_time` (DateTime, nullable), `end_time` (DateTime, nullable), `printer_name` (String(256), nullable), and `comment` (String(1024), nullable).
   - `print_job_spool`: Table with columns `id` (Integer, PK), `print_job_id` (Integer, FK to `print_job.id`, non-nullable), `spool_id` (Integer, FK to `spool.id`, non-nullable), and `weight_used` (Float, non-nullable).

2. **SQLAlchemy DB Models (`spoolman/database/models.py`)**:
   - Lines 121-171 define the SQLAlchemy classes:
     ```python
     class Project(Base):
         __tablename__ = "project"
         id: Mapped[int] = mapped_column(primary_key=True, index=True)
         registered: Mapped[datetime] = mapped_column()
         name: Mapped[str] = mapped_column(String(256))
         description: Mapped[str | None] = mapped_column(String(1024))
         link: Mapped[str | None] = mapped_column(String(1024))
         plates: Mapped[list["Plate"]] = relationship(back_populates="project")

     class Plate(Base):
         __tablename__ = "plate"
         id: Mapped[int] = mapped_column(primary_key=True, index=True)
         registered: Mapped[datetime] = mapped_column()
         project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
         project: Mapped["Project"] = relationship(back_populates="plates")
         name: Mapped[str] = mapped_column(String(256))
         file_path: Mapped[str | None] = mapped_column(String(1024))
         estimated_weight: Mapped[float | None] = mapped_column()
         estimated_time: Mapped[int | None] = mapped_column(comment="Estimated time in seconds")
         comment: Mapped[str | None] = mapped_column(String(1024))
         print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="plate")

     class PrintJob(Base):
         __tablename__ = "print_job"
         id: Mapped[int] = mapped_column(primary_key=True, index=True)
         registered: Mapped[datetime] = mapped_column()
         plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"))
         plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
         status: Mapped[str] = mapped_column(String(64))
         start_time: Mapped[datetime | None] = mapped_column()
         end_time: Mapped[datetime | None] = mapped_column()
         printer_name: Mapped[str | None] = mapped_column(String(256))
         comment: Mapped[str | None] = mapped_column(String(1024))
         spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")

     class PrintJobSpool(Base):
         __tablename__ = "print_job_spool"
         id: Mapped[int] = mapped_column(primary_key=True, index=True)
         print_job_id: Mapped[int] = mapped_column(ForeignKey("print_job.id"))
         print_job: Mapped["PrintJob"] = relationship(back_populates="spool_usages")
         spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"))
         spool: Mapped["Spool"] = relationship()
         weight_used: Mapped[float] = mapped_column()
     ```

3. **Existing Integration Tests structure (`tests_integration/tests/`)**:
   - `tests_integration/tests/conftest.py` defines standard integration test runner helpers and fixtures (`random_vendor`, `random_filament`, `assert_dicts_compatible`, `URL`).
   - `spool/test_add.py` and `spool/test_use.py` verify model CRUD and spool remaining weight logic by sending HTTP POST, PUT, and DELETE commands to Spoolman endpoints.
   - Example HTTP pattern from `spool/test_add.py`:
     ```python
     result = httpx.post(f"{URL}/api/v1/spool", json={...})
     result.raise_for_status()
     # verify...
     httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
     ```

---

## 2. Logic Chain

1. **Mapping to REST Endpoints**: Since the existing code defines `Project`, `Plate`, and `PrintJob` models, and other entities (Vendor, Filament, Spool) are exposed via `/api/v1/<entity>` endpoints, the 3D Print Management entities will follow the same pattern:
   - `/api/v1/project`
   - `/api/v1/plate`
   - `/api/v1/print_job`
2. **Pytest Integration Runner**: The integration tests are run inside a Docker-compose environment (SQLite, PG, MariaDB, CockroachDB) as defined in `tests_integration/run.py`. Any new tests should be standard pytest files matching `test_*.py` format to automatically be run by pytest.
3. **Hierarchy of Tiers**:
   - **Tier 1 (CRUD)** ensures basic POST, GET, PATCH, DELETE operations work for each entity without errors.
   - **Tier 2 (Boundary & Relationships)** verifies integrity constraints (such as non-existent project/plate/spool foreign keys, negative weights, etc.) return HTTP 400/404/422.
   - **Tier 3 (Multi-Entity Workflow)** tests a composite sequence of actions (Creating a Project -> adding a Plate -> starting a Print Job using a Spool) simulating user navigation.
   - **Tier 4 (Business Logic - Automatic Weight Deduction)** tests that when a print job's status is set to `successful`, it automatically updates the associated spool's `used_weight` and `remaining_weight` (with idempotency check and clamping to zero).

---

## 3. Caveats

1. **API Routing Registration**: The REST API routes are not yet registered in `spoolman/api/v1/router.py`. The design assumes standard endpoints (`/api/v1/project`, `/api/v1/plate`, `/api/v1/print_job`) and request formats.
2. **Cascade Deletes**: If a Project is deleted, its associated Plates must either cascade delete or fail (foreign key constraint error). Similarly, deleting a Plate must affect associated Print Jobs. In our design, we recommend asserting standard constraint failure (HTTP 400/409 conflict) or cascade deletion depending on implementation preference. The test specifications below verify constraint failures for clean integrity management.

---

## 4. Conclusion

Below is the design specification for the integration test cases.

### A. New Integration Test Fixtures (to be added to `tests_integration/tests/conftest.py`)

Propose the following helper context managers and fixtures to automate resource creation and teardown in tests:

```python
@contextmanager
def random_project_impl():
    """Context manager for creating a project and deleting it on exit."""
    result = httpx.post(
        f"{URL}/api/v1/project",
        json={
            "name": "Integration Test Project",
            "description": "A project for testing CRUD operations",
            "link": "http://example.com/test-project",
        },
    )
    result.raise_for_status()
    project = result.json()
    yield project
    httpx.delete(f"{URL}/api/v1/project/{project['id']}").raise_for_status()

@pytest.fixture
def random_project():
    """Fixture to obtain a random project."""
    with random_project_impl() as project:
        yield project

@contextmanager
def random_plate_impl(project_id: int):
    """Context manager for creating a plate under a project."""
    result = httpx.post(
        f"{URL}/api/v1/plate",
        json={
            "project_id": project_id,
            "name": "Plate Alpha",
            "file_path": "projects/test/plate_alpha.gcode",
            "estimated_weight": 42.5,
            "estimated_time": 7200,
            "comment": "PLA test plate",
        },
    )
    result.raise_for_status()
    plate = result.json()
    yield plate
    httpx.delete(f"{URL}/api/v1/plate/{plate['id']}").raise_for_status()

@pytest.fixture
def random_plate(random_project):
    """Fixture to obtain a random plate."""
    with random_plate_impl(random_project["id"]) as plate:
        yield plate

@contextmanager
def random_print_job_impl(plate_id: int):
    """Context manager for creating a print job under a plate."""
    result = httpx.post(
        f"{URL}/api/v1/print_job",
        json={
            "plate_id": plate_id,
            "status": "pending",
            "printer_name": "Ender 3",
            "comment": "Initial test job",
            "spool_usages": [],
        },
    )
    result.raise_for_status()
    print_job = result.json()
    yield print_job
    httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}").raise_for_status()

@pytest.fixture
def random_print_job(random_plate):
    """Fixture to obtain a random print job."""
    with random_print_job_impl(random_plate["id"]) as print_job:
        yield print_job
```

---

### B. Integration Test Specifications

#### **Tier 1: CRUD API Endpoints**
*Target Files: `test_project_crud.py`, `test_plate_crud.py`, `test_print_job_crud.py`*

1. **Project CRUD Operations** (`test_project_crud.py`)
   - **`test_create_project`**:
     - **Action**: `POST /api/v1/project` with payload `{"name": "Spec Project", "description": "Desc", "link": "http://lnk"}`.
     - **Verification**: HTTP 201/200, checks `name`, `description`, `link` are returned correctly, and `id` and `registered` fields are auto-populated.
   - **`test_get_project`**:
     - **Action**: `GET /api/v1/project/{project_id}`.
     - **Verification**: HTTP 200, contents match the created project.
   - **`test_list_projects`**:
     - **Action**: `GET /api/v1/project?name=Spec&sort=name:asc`.
     - **Verification**: HTTP 200, checks response list contains the project, checks `x-total-count` header is correct.
   - **`test_patch_project`**:
     - **Action**: `PATCH /api/v1/project/{project_id}` with updated fields `{"name": "New Name"}`.
     - **Verification**: HTTP 200, returns the updated project object.
   - **`test_delete_project`**:
     - **Action**: `DELETE /api/v1/project/{project_id}`.
     - **Verification**: HTTP 200/204. A subsequent `GET` to the same ID returns HTTP 404.

2. **Plate CRUD Operations** (`test_plate_crud.py`)
   - **`test_create_plate`**:
     - **Action**: `POST /api/v1/plate` under a valid project.
     - **Verification**: HTTP 201/200, returns correct fields.
   - **`test_get_plate`**:
     - **Action**: `GET /api/v1/plate/{plate_id}`.
     - **Verification**: HTTP 200.
   - **`test_list_plates`**:
     - **Action**: `GET /api/v1/plate?project_id={project_id}`.
     - **Verification**: HTTP 200, lists plates linked to project.
   - **`test_patch_plate`**:
     - **Action**: `PATCH /api/v1/plate/{plate_id}` with `{"estimated_weight": 60.0}`.
     - **Verification**: HTTP 200.
   - **`test_delete_plate`**:
     - **Action**: `DELETE /api/v1/plate/{plate_id}`.
     - **Verification**: HTTP 200. Subsequent `GET` returns 404.

3. **Print Job CRUD Operations** (`test_print_job_crud.py`)
   - **`test_create_print_job`**:
     - **Action**: `POST /api/v1/print_job` under a valid plate with status `"printing"`.
     - **Verification**: HTTP 201/200, status is `"printing"`, `spool_usages` is empty.
   - **`test_get_print_job`**:
     - **Action**: `GET /api/v1/print_job/{print_job_id}`.
     - **Verification**: HTTP 200.
   - **`test_list_print_jobs`**:
     - **Action**: `GET /api/v1/print_job?status=printing`.
     - **Verification**: HTTP 200.
   - **`test_patch_print_job`**:
     - **Action**: `PATCH /api/v1/print_job/{print_job_id}` with `{"printer_name": "Prusa i3"}`.
     - **Verification**: HTTP 200.
   - **`test_delete_print_job`**:
     - **Action**: `DELETE /api/v1/print_job/{print_job_id}`.
     - **Verification**: HTTP 200. Subsequent `GET` returns 404.

---

#### **Tier 2: Boundary Conditions and Relationships**
*Target Files: `test_boundaries.py`*

1. **Project Boundary Validation**:
   - **`test_create_project_empty_name`**: POST a project with empty name `{"name": ""}`. Expected: HTTP 400.
   - **`test_create_project_long_name`**: POST name with 257 characters. Expected: HTTP 400.

2. **Plate Relationship Validation**:
   - **`test_create_plate_invalid_project_id`**: POST a plate with `project_id = 999999` (non-existent). Expected: HTTP 400 or HTTP 404.
   - **`test_create_plate_negative_inputs`**: POST `{"estimated_weight": -10.0}` or `{"estimated_time": -3600}`. Expected: HTTP 400.

3. **Print Job Relationship & Constraint Validation**:
   - **`test_create_print_job_invalid_plate_id`**: POST print job with `plate_id = 999999`. Expected: HTTP 400/404.
   - **`test_create_print_job_invalid_spool_id`**: POST print job with spool usages including non-existent `spool_id`: `[{"spool_id": 999999, "weight_used": 10.0}]`. Expected: HTTP 400/404.
   - **`test_create_print_job_negative_weight`**: POST print job with negative weight: `[{"spool_id": valid_spool_id, "weight_used": -5.0}]`. Expected: HTTP 400.

4. **Foreign Key Integrity Cascades**:
   - **`test_delete_project_fails_with_plates`**: Attempt to `DELETE /api/v1/project/{project_id}` when the project has associated plates. Expected: HTTP 400 / HTTP 409 (Conflict) to prevent orphan plates.
   - **`test_delete_plate_fails_with_print_jobs`**: Attempt to `DELETE /api/v1/plate/{plate_id}` when the plate has associated print jobs. Expected: HTTP 400 / HTTP 409 (Conflict).

---

#### **Tier 3: Cross-Feature Integration**
*Target File: `test_workflow.py`*

1. **`test_integrated_print_workflow`**:
   - **Setup**: Create a filament and a spool (`start_weight` = 1000g).
   - **Step 1**: Create a Project.
   - **Step 2**: Create a Plate under that project.
   - **Step 3**: Create a Print Job under that plate with status `"printing"`, linked to the spool with `weight_used` = 250g. Verify the print job lists the spool usages correctly.
   - **Step 4**: Verify Spool's remaining weight is still 1000g (status is `"printing"`, not `"successful"`).
   - **Step 5**: Update the Print Job status to `"failed"`. Verify spool remaining weight remains 1000g.
   - **Step 6**: Delete the print job, then the plate, then the project, then the spool and filament. Verify no residual errors or constraint blocks.

---

#### **Tier 4: Business Logic Rule (Automatic Weight Deduction)**
*Target File: `test_weight_deduction.py`*

1. **`test_deduct_on_status_successful`**:
   - **Setup**: Create a spool with `remaining_weight` = 1000g and `used_weight` = 0g.
   - **Step 1**: Create a Print Job with status `"printing"`, linking the spool with `weight_used` = 150g.
   - **Step 2**: Check spool remaining weight via `GET /api/v1/spool/{spool_id}`. Verify it is still 1000g.
   - **Step 3**: `PATCH /api/v1/print_job/{id}` to update status to `"successful"`.
   - **Step 4**: Verify spool remaining weight is now 850g and `used_weight` is 150g.

2. **`test_deduct_on_creation_if_successful`**:
   - **Setup**: Create a spool with `remaining_weight` = 1000g.
   - **Step 1**: Create a Print Job directly with status `"successful"`, using `weight_used` = 200g.
   - **Step 2**: Verify the spool's remaining weight is immediately updated to 800g and `used_weight` is 200g.

3. **`test_deduct_multiple_spools`**:
   - **Setup**: Create two spools: Spool A (remaining 1000g) and Spool B (remaining 500g).
   - **Step 1**: Create a Print Job with status `"printing"`, containing spool usages: `[{"spool_id": A, "weight_used": 100g}, {"spool_id": B, "weight_used": 50g}]`.
   - **Step 2**: PATCH print job status to `"successful"`.
   - **Step 3**: Verify Spool A has `remaining_weight` = 900g and Spool B has `remaining_weight` = 450g.

4. **`test_deduction_idempotency`**:
   - **Setup**: Create a spool with `remaining_weight` = 1000g.
   - **Step 1**: Create a Print Job with status `"printing"`, usage of 100g.
   - **Step 2**: PATCH status to `"successful"`. Verify remaining weight is 900g.
   - **Step 3**: PATCH print job again to update comment, keeping status as `"successful"`.
   - **Step 4**: Verify remaining weight is still 900g (it should not deduct twice).

5. **`test_deduction_greater_than_remaining_clamps`**:
   - **Setup**: Create a spool with `remaining_weight` = 50g.
   - **Step 1**: Create a Print Job with status `"printing"`, usage of 100g.
   - **Step 2**: PATCH status to `"successful"`.
   - **Step 3**: Verify the spool's remaining weight is clamped to 0g (no negative weight allowed).

---

## 5. Verification Method

To verify the test suite:
1. When the backend endpoints and tests are written, they can be run using the standard integration suite runner:
   ```bash
   python tests_integration/run.py sqlite
   ```
2. Inspect test output logs. All tests under `tests_integration/tests/project/`, `tests_integration/tests/plate/`, and `tests_integration/tests/print_job/` should execute and report status.
3. Invalidation conditions:
   - If a test fails because the status code is 422 instead of 400, verify the validation framework's expected status codes for client-side errors in FastAPI (FastAPI yields 422 Unprocessable Entity for body validations by default; check if Spoolman has custom exception handlers converting them to 400).
   - If weight deduction is not visible on the spool, check whether the backend triggers weight deduction in `PATCH` handlers by querying the DB directly or sending GET requests to the spool API.
