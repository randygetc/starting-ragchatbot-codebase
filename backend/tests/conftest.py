import sys
import os

# Add backend/ to path so test files can import backend modules directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_ANSWER = "This is a test answer from the RAG system."
SAMPLE_SOURCES = ["Python Basics - Lesson 1", "Python Basics - Lesson 2"]
SAMPLE_SESSION_ID = "test-session-123"
SAMPLE_COURSES = ["Python Basics", "Machine Learning 101", "Web Development"]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """RAGSystem with all external dependencies mocked and sensible defaults."""
    mock = MagicMock()
    mock.query.return_value = (SAMPLE_ANSWER, SAMPLE_SOURCES)
    mock.session_manager.create_session.return_value = SAMPLE_SESSION_ID
    mock.get_course_analytics.return_value = {
        "total_courses": len(SAMPLE_COURSES),
        "course_titles": SAMPLE_COURSES,
    }
    return mock


@pytest.fixture
def test_app(mock_rag_system):
    """
    Minimal FastAPI app mirroring app.py routes without static file mounting.

    Avoids the ../frontend directory requirement that makes importing app.py
    directly fail in the test environment.
    """
    app = FastAPI(title="Test RAG App")

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[str]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        mock_rag_system.session_manager.clear_session(session_id)
        return {"status": "cleared"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """Synchronous TestClient wrapping the test app."""
    return TestClient(test_app)
