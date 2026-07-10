# Handoff Report — Integration Tests Review (E2E-2)

## 1. Observation

### Code Layout & File Locations
The files under review were found at the root of `tests_integration/tests/` instead of their respective subdirectories:
- `tests_integration/tests/test_project_crud.py`
- `tests_integration/tests/test_plate_crud.py`
- `tests_integration/tests/test_print_job_crud.py`
- `tests_integration/tests/test_boundaries.py`
- `tests_integration/tests/test_workflow.py`
- `tests_integration/tests/test_weight_deduction.py`

This conflicts with `PROJECT.md` line 16:
```markdown
- Integration tests: tests_integration/tests/project/, tests_integration/tests/plate/, tests_integration/tests/print_job/.
```

### Unused Imports
Multiple files under review import unused modules:
- `tests_integration/tests/test_project_crud.py`:
  - Line 4: `import pytest`
  - Line 7: `from .conftest import URL, assert_dicts_compatible` (`assert_dicts_compatible` is unused)
- `tests_integration/tests/test_plate_crud.py`:
  - Line 4: `import pytest`
  - Line 7: `from .conftest import URL, assert_dicts_compatible` (`assert_dicts_compatible` is unused)
- `tests_integration/tests/test_print_job_crud.py`:
  - Line 4: `import pytest`
  - Line 7: `from .conftest import URL, assert_dicts_compatible` (`assert_dicts_compatible` is unused)
- `tests_integration/tests/test_boundaries.py`:
  - Line 4: `import pytest`
- `tests_integration/tests/test_workflow.py`:
  - Line 4: `import pytest`

### Test Execution Output
Attempting to execute the test suite via `python tests_integration/run.py sqlite` yielded the following timeout error due to non-interactive execution constraints:
```
Encountered error in step execution: Permission prompt for action 'command' on target 'python tests_integration/run.py sqlite' timed out waiting for user response. The user was not able to provide permission on time. You should proceed as much as possible without access to this resource.
```

### Backend Implementation Status
`spoolman/api/v1/router.py` does not include routers for `project`, `plate`, or `print_job`:
```python
# Add routers
app.include_router(filament.router)
app.include_router(spool.router)
app.include_router(vendor.router)
app.include_router(setting.router)
app.include_router(field.router)
app.include_router(other.router)
app.include_router(externaldb.router)
app.include_router(export.router)
```
This confirms that the endpoints are not implemented yet (milestone `IMP-1`), meaning that the integration tests are expected to fail with `404 Not Found` or `405 Method Not Allowed` when run.

---

## 2. Logic Chain

1. **Observation 1 (Layout)**: `PROJECT.md` dictates that tests for `project`, `plate`, and `print_job` should reside in subdirectories: `tests_integration/tests/project/`, `tests_integration/tests/plate/`, and `tests_integration/tests/print_job/`.
2. **Inference 1**: Placing these tests directly under `tests_integration/tests/` violates the project layout contract. They must be moved into the correct directories.
3. **Observation 2 (Unused Imports)**: Multiple test files import `pytest` and/or `assert_dicts_compatible` without using them.
4. **Inference 2**: Unused imports violate Python's PEP 8 styling conventions and specifically fail Ruff's `F401` rule, which is configured via `pyproject.toml` (using `select = ["ALL"]`). This will cause lint checks to fail.
5. **Observation 3 (Test Failures)**: The backend API and routers for Project, Plate, and PrintJob are not registered in `spoolman/api/v1/router.py` (which is planned for `IMP-1`).
6. **Inference 3**: Executing the integration tests will result in expected `404 Not Found` or `405 Method Not Allowed` failures since the corresponding REST routes do not exist.
7. **Observation 4 (Masked Failures in `test_boundaries.py`)**: `test_delete_project_fails_with_plates` and `test_delete_plate_fails_with_print_jobs` perform assertions and then clean up in `finally` blocks. If the assertion fails (e.g. project deletion mistakenly succeeds), cascade delete may destroy the child entity, causing the `finally` cleanup to raise a `404` error and mask the assertion failure.
8. **Inference 4**: The test cleanups in the boundary files need to handle `404` errors gracefully so as not to mask assertion failures.

---

## 3. Caveats

- We were unable to execute the dockerized integration tests directly due to the command permission prompt timing out in this automated environment.
- We assume that the backend development (`IMP-1`) will implement the REST API specifications exactly as declared in `PROJECT.md`.

---

## 4. Conclusion

The integration test suite is logically complete and well-structured, but requires changes to adhere to Spoolman's code layout, code quality/linting rules, and to resolve subtle test assertion masking bugs.

### Verdict: REQUEST_CHANGES

---

## Quality Review Report

### Findings

#### [Major] Finding 1: Code Layout Violation
- **What**: Integration tests for `project`, `plate`, and `print_job` are located at the root of `tests_integration/tests/` instead of their respective subdirectories.
- **Where**: `/Users/yalazi/Documents/PROJECTS/software/Spoolman/tests_integration/tests/`
- **Why**: Violates `PROJECT.md` line 16 and contradicts the existing layout (e.g., `tests_integration/tests/vendor/`, `tests_integration/tests/spool/`).
- **Suggestion**: Create folders `project/`, `plate/`, and `print_job/` and move the respective CRUD tests into them.

#### [Minor] Finding 2: Unused Imports
- **What**: Unused imports of `pytest` and `assert_dicts_compatible` in multiple test files.
- **Where**:
  - `test_project_crud.py` (Lines 4, 7)
  - `test_plate_crud.py` (Lines 4, 7)
  - `test_print_job_crud.py` (Lines 4, 7)
  - `test_boundaries.py` (Line 4)
  - `test_workflow.py` (Line 4)
- **Why**: Violates Ruff lint rules (`F401`) configured in `pyproject.toml`.
- **Suggestion**: Remove unused imports.

---

### Verified Claims

- **Fixtures implementation in `conftest.py`** → verified via static review → **PASS**
- **Test execution status (Expected Failures)** → verified via static check of `spoolman/api/v1/router.py` → **PASS** (FastAPI routers for these endpoints are missing, which correctly guarantees 404/405 errors).

---

### Coverage Gaps

- **Print job start/end time validation** — risk level: **Medium** — recommendation: **Investigate/Implement** (Add boundary tests in `test_boundaries.py` verifying that a print job's `end_time` cannot be set chronologically before its `start_time`).
- **Weight deduction clamp behavior verification** — risk level: **Low** — recommendation: **Investigate/Implement** (Add an assertion in `test_deduction_greater_than_remaining_clamps` verifying the expected value of `used_weight` when `remaining_weight` is clamped to `0.0`).
- **State transition reversibility / refund** — risk level: **High** — recommendation: **Investigate/Implement** (Add tests in `test_weight_deduction.py` verifying if transitioning status from `successful` back to `failed` or `printing`, or deleting a `successful` job, refunds/restores the weight on the spool).

---

### Unverified Items

- **Actual containerized execution of tests** — reason: command permission prompt timed out.

---

## Adversarial Review Report

### Challenge Summary

**Overall risk assessment**: **MEDIUM**

### Challenges

#### [High] Challenge 1: Cleanup Masking Assertion Failures
- **Assumption challenged**: The test assertions will be reported accurately if a delete constraint is violated.
- **Attack scenario**: In `test_delete_project_fails_with_plates`, if the project deletion mistakenly succeeds (a bug in the backend), the assertion fails. However, the subsequent `finally` block executes `httpx.delete(f".../plate/{plate['id']}").raise_for_status()`. Since the project was deleted, cascade delete might have already deleted the plate. The cleanup will fail with a `404 Client Error: Not Found` exception, masking the original assertion failure.
- **Blast radius**: Developers will see a generic `HTTPStatusError` during cleanup, leading to difficult debugging and masking the actual failure of the foreign key constraint assertion.
- **Mitigation**: Adjust the cleanup in `finally` blocks to catch/ignore `404` errors or verify existence before deleting.

---

### Stress Test Results

- **Project/Plate/Print Job Name boundaries** → Expect `400/422` error on empty name or excessively long name (257+ chars) → verified via `test_boundaries.py` → **PASS** (Tests are designed to catch this).
- **Negative weight/time inputs** → Expect rejection → verified via `test_boundaries.py` → **PASS**.

---

### Unchallenged Areas

- **Concurrency** — reason: out of scope for E2E-2 test design.

---

## 5. Verification Method

To verify these findings and execute the tests locally:
1. Move the CRUD files into the proper directory structure:
   - Move `test_project_crud.py` to `project/`
   - Move `test_plate_crud.py` to `plate/`
   - Move `test_print_job_crud.py` to `print_job/`
2. Remove unused imports in all test files.
3. Run the integration test suite:
   ```bash
   python tests_integration/run.py sqlite
   ```
4. Confirm that the new tests fail with 404 or 405 error codes.
