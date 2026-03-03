# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# From repo root
./run.sh

# Or manually
cd backend && UV_HTTP_TIMEOUT=300 uv run uvicorn app:app --reload --port 8000
```

App runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

**Prerequisites:** Create a `.env` file in the repo root with `ANTHROPIC_API_KEY=<key>`. The `.env` is already gitignored.

Install dependencies (first run may download ~2GB of CUDA/torch packages):
```bash
UV_HTTP_TIMEOUT=300 uv sync
```

**Dependency Management:** Always use `uv` to manage all dependencies. Never use `pip` directly.
- Add a package: `uv add <package>`
- Remove a package: `uv remove <package>`
- Sync environment: `UV_HTTP_TIMEOUT=300 uv sync`

## Architecture

This is a full-stack RAG (Retrieval-Augmented Generation) chatbot. The FastAPI backend serves both the API and the static frontend.

### Request Flow

1. User submits a query → `POST /api/query` (with `session_id`)
2. `RAGSystem.query()` orchestrates the response:
   - Fetches conversation history from `SessionManager`
   - Calls `AIGenerator.generate_response()` with a `search_course_content` tool available
3. Claude decides whether to search. If yes (`stop_reason == "tool_use"`):
   - `CourseSearchTool` queries ChromaDB via `VectorStore.search()`
   - Results returned to Claude in a second API call
4. Final answer + sources returned to frontend, exchange saved to session

### Key Design Decisions

- **Agentic tool-use loop**: Claude autonomously decides whether to search or answer from general knowledge. It is instructed to search at most once per query.
- **Two ChromaDB collections**: `course_catalog` (course-level metadata for fuzzy name resolution) and `course_content` (chunked lesson text for semantic search).
- **Session history**: Stored in-memory in `SessionManager`, capped at last 2 exchanges (4 messages). History is injected into the system prompt, not as message turns.
- **Deduplication on startup**: `add_course_folder()` checks existing course titles in ChromaDB and skips already-indexed files.

### Backend Modules (`backend/`)

| File | Role |
|------|------|
| `app.py` | FastAPI routes, startup event to load `docs/`, serves frontend as static files |
| `rag_system.py` | Central orchestrator — wires all components together |
| `ai_generator.py` | Anthropic API client; handles tool-use two-turn loop |
| `vector_store.py` | ChromaDB wrapper; semantic course name resolution + content search |
| `document_processor.py` | Parses course `.txt` files; sentence-aware chunking with overlap |
| `search_tools.py` | `Tool` ABC, `CourseSearchTool`, `ToolManager` registry |
| `session_manager.py` | In-memory session store, conversation history formatting |
| `models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |
| `config.py` | Central config dataclass (chunk size, overlap, model name, paths) |

### Course Document Format

Files in `docs/` must follow this structure for the parser in `document_processor.py`:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
<lesson content...>

Lesson 2: <title>
...
```

Supported file types: `.txt`, `.pdf`, `.docx`.

### Configuration (`backend/config.py`)

Key defaults:
- `ANTHROPIC_MODEL`: `claude-sonnet-4-20250514`
- `EMBEDDING_MODEL`: `all-MiniLM-L6-v2` (via sentence-transformers)
- `CHUNK_SIZE`: 800 chars, `CHUNK_OVERLAP`: 100 chars
- `MAX_RESULTS`: 5 chunks per search, `MAX_HISTORY`: 2 exchanges
- `CHROMA_PATH`: `./chroma_db` (relative to `backend/`)
