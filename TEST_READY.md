# E2E Test Suite Ready

## Test Runner
- Command: `python tests_integration/run.py sqlite`
- Expected: all tests pass with exit code 0 (once backend is implemented)

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 15 | CRUD operations for Projects, Plates, and Print Jobs |
| 2. Boundary & Corner | 10 | Boundary and relationship validations (name constraints, negative inputs, invalid FKs, chronological times, cascade blocks) |
| 3. Cross-Feature | 1 | Multi-entity integrated print workflow (filament/spool -> project -> plate -> print job) |
| 4. Real-World Application | 6 | Spool weight deduction business logic (creation, status update, multi-spool, idempotency, clamping, refunds) |
| **Total** | **32** | |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| Project Management | 5 | 2 | ✓ | N/A |
| Plate Management | 5 | 3 | ✓ | N/A |
| Print Job Management | 5 | 5 | ✓ | N/A |
| Spool Weight Deduction | N/A | N/A | ✓ | 6 |
