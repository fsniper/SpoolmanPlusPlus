# Scope: Implementation Track

## Architecture
- Backend: FastAPI controllers and SQLAlchemy DB CRUD models.
- Frontend: Refine React components inside `client/src/pages/` using Ant Design.
- Integration: Pass tests defined in `tests_integration/`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| IMP-1 | Backend API & CRUD | Implement Pydantic models, DB CRUD, and routers for Project, Plate, PrintJob | None | DONE |
| IMP-2 | Weight Deduction Logic | Implement automatic remaining weight deduction for successful print jobs | IMP-1 | IN_PROGRESS |
| IMP-3 | Refine Frontend UI | Build Projects, Plates, and Print Jobs React pages using Refine and AntD | IMP-2 | PLANNED |
| IMP-4 | Verification & Polish | Verify all tests pass, frontend builds successfully, and perform audit | IMP-3 | PLANNED |
