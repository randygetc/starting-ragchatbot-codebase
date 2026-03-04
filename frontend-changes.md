# Frontend Changes: Dark/Light Theme Toggle

## Overview
Added a dark/light theme toggle button to the chat UI. Users can switch between themes at any time; their preference is persisted in `localStorage`.

---

## Files Modified

### `frontend/index.html`
- Bumped CSS cache-buster: `style.css?v=11` → `style.css?v=12`
- Bumped JS cache-buster: `script.js?v=10` → `script.js?v=11`
- Added a fixed-position `<button id="themeToggle" class="theme-toggle">` at the top of `<body>` (before `.container`), containing:
  - A **moon SVG** (`.icon-moon`) — visible in dark mode
  - A **sun SVG** (`.icon-sun`) — visible in light mode
  - `aria-label="Toggle light/dark theme"` and `title="Toggle theme"` for accessibility

### `frontend/style.css`
1. **New CSS variable `--code-bg`** added to `:root` (`rgba(0,0,0,0.2)`) and used in `.message-content code` and `.message-content pre` instead of hardcoded values.

2. **Light theme block** `[data-theme="light"]` overrides all design-token variables:
   | Variable | Light value |
   |---|---|
   | `--background` | `#f8fafc` |
   | `--surface` | `#ffffff` |
   | `--surface-hover` | `#f1f5f9` |
   | `--text-primary` | `#0f172a` |
   | `--text-secondary` | `#64748b` |
   | `--border-color` | `#e2e8f0` |
   | `--shadow` | `0 4px 6px -1px rgba(0,0,0,0.1)` |
   | `--welcome-bg` | `#eff6ff` |
   | `--code-bg` | `rgba(0,0,0,0.05)` |
   Primary/accent colors remain the same as dark mode.

3. **Smooth transition helper** — `html.theme-transitioning` (and all its descendants) gets a 0.3 s ease transition on `background-color`, `color`, `border-color`, and `box-shadow` via `!important`. The class is added/removed by JavaScript around every theme switch.

4. **`.theme-toggle` styles** — fixed `40×40 px` circular button, top-right corner (`top: 1rem; right: 1rem; z-index: 100`). Hover lifts the button with `translateY(-1px)` and applies `--primary-color` tint. Focus shows a `--focus-ring` outline.

5. **Icon show/hide logic** via CSS:
   - Default (dark): `.icon-moon` visible, `.icon-sun` rotated and invisible.
   - `[data-theme="light"]`: `.icon-sun` visible, `.icon-moon` rotated and invisible.
   Icons cross-fade with a 0.2 s opacity + rotation transition.

### `frontend/script.js`
- **`initTheme()`** — reads `localStorage.getItem('theme')` (defaults to `'dark'`) and sets `document.documentElement.setAttribute('data-theme', savedTheme)`. Called immediately (before `DOMContentLoaded`) to prevent flash of wrong theme.
- **`toggleTheme()`** — reads current `data-theme`, flips to the other value, saves to `localStorage`, and temporarily adds/removes `theme-transitioning` class on `<html>` for the smooth CSS transition.
- **Event listener** for `#themeToggle` wired up inside `setupEventListeners()`.

---

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
