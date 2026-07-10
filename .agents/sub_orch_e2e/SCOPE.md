# Scope: E2E Testing Track

## Architecture
- Target: Integration test suite for Projects, Plates, and Print Jobs.
- Testing Framework: `pytest` and `httpx`.
- Environment: Docker compose target running Spoolman (defined in `tests_integration/docker-compose-sqlite.yml` etc.).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| E2E-1 | Test Design | Define integration test specifications | None | DONE |
| E2E-2 | Integration Test Suite | Implement integration test cases and publish `TEST_READY.md` | E2E-1 | DONE |
