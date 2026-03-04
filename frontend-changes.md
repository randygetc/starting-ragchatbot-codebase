# Testing Infrastructure Changes

## Summary

Enhanced the testing framework for the RAG chatbot backend with API endpoint tests, pytest configuration, and shared test fixtures.

---

## Files Modified

### `pyproject.toml`
- Added `httpx>=0.27.0` to the `dev` dependency group (required by FastAPI's `TestClient`)
- Added `[tool.pytest.ini_options]` section:
  - `testpaths = ["backend/tests"]` — pytest discovers tests without needing `cd backend/tests`
  - `pythonpath = ["backend"]` — makes backend modules importable in tests without manual `sys.path` hacks
  - `addopts = "-v"` — verbose output by default

### `backend/tests/conftest.py`
- Kept the existing `sys.path` insertion for backwards compatibility
- Added shared test data constants: `SAMPLE_ANSWER`, `SAMPLE_SOURCES`, `SAMPLE_SESSION_ID`, `SAMPLE_COURSES`
- Added `mock_rag_system` fixture: a `MagicMock` replacing `RAGSystem` with sensible defaults for all API paths
- Added `test_app` fixture: an inline `FastAPI` app that mirrors the three API routes from `app.py` (`POST /api/query`, `GET /api/courses`, `DELETE /api/session/{id}`) **without** mounting static files — avoids the `../frontend` directory requirement that breaks imports in the test environment
- Added `client` fixture: a `TestClient` wrapping `test_app` for synchronous HTTP testing

---

## Files Added

### `backend/tests/test_api.py`
API endpoint tests covering all three routes:

**`POST /api/query`** (13 tests)
- Returns 200 with answer, sources, and session_id on valid request
- Auto-creates a session when no `session_id` is provided
- Uses the provided `session_id` without creating a new one
- Forwards query and session_id to `RAGSystem.query()`
- Returns 500 with detail message when `RAGSystem.query()` raises
- Returns 422 for missing required `query` field

**`GET /api/courses`** (8 tests)
- Returns 200 with `total_courses` and `course_titles`
- Calls `RAGSystem.get_course_analytics()` once per request
- Returns 500 with detail message on exception
- Handles empty course list correctly

**`DELETE /api/session/{session_id}`** (4 tests)
- Returns 200 with `{"status": "cleared"}`
- Forwards the session ID to `SessionManager.clear_session()`
- Correctly routes different session IDs across multiple calls

---

## Design Decisions

- **Inline test app instead of importing `app.py`**: `app.py` mounts `StaticFiles(directory="../frontend")` at module level, which raises an error when `../frontend` does not exist. Defining routes inline in the `test_app` fixture avoids the need to patch the filesystem or mock `StaticFiles`.
- **Function-scoped fixtures**: All fixtures use the default function scope, ensuring each test gets a fresh mock with no cross-test state bleed.
- **No `pytest-asyncio` needed**: FastAPI's `TestClient` wraps the ASGI app in a synchronous interface, so async route handlers are tested without any async test framework.
