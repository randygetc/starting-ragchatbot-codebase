"""
Tests for FastAPI endpoints in app.py

Covers:
- POST /api/query  — success with session_id, auto-created session, error propagation
- GET  /api/courses — returns total_courses + course_titles, error propagation
- DELETE /api/session/{session_id} — clears session and returns status

Uses the `client` and `mock_rag_system` fixtures from conftest.py.
The test app is defined inline in conftest.py to avoid the static-file
mounting in the real app.py (which requires ../frontend to exist).
"""
import pytest
from conftest import (
    SAMPLE_ANSWER,
    SAMPLE_COURSES,
    SAMPLE_SESSION_ID,
    SAMPLE_SOURCES,
)


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_returns_200_on_valid_request(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.status_code == 200

    def test_response_contains_answer(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.json()["answer"] == SAMPLE_ANSWER

    def test_response_contains_sources(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.json()["sources"] == SAMPLE_SOURCES

    def test_response_contains_session_id_when_provided(self, client):
        resp = client.post(
            "/api/query",
            json={"query": "What is Python?", "session_id": "my-session"},
        )
        assert resp.json()["session_id"] == "my-session"

    def test_auto_creates_session_when_none_provided(self, client):
        resp = client.post("/api/query", json={"query": "What is Python?"})
        assert resp.json()["session_id"] == SAMPLE_SESSION_ID

    def test_calls_create_session_when_no_session_id(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "test"})
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_does_not_create_session_when_session_id_provided(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "test", "session_id": "existing"})
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_passes_query_to_rag_system(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "How does recursion work?"})
        called_query = mock_rag_system.query.call_args[0][0]
        assert called_query == "How does recursion work?"

    def test_passes_session_id_to_rag_system(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "test", "session_id": "sess-42"})
        mock_rag_system.query.assert_called_once_with("test", "sess-42")

    def test_returns_500_when_rag_raises(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")
        resp = client.post("/api/query", json={"query": "test"})
        assert resp.status_code == 500

    def test_500_response_contains_error_detail(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("DB unavailable")
        resp = client.post("/api/query", json={"query": "test"})
        assert "DB unavailable" in resp.json()["detail"]

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/query", json={"session_id": "s1"})
        assert resp.status_code == 422

    def test_empty_query_is_accepted(self, client):
        resp = client.post("/api/query", json={"query": ""})
        assert resp.status_code == 200

    def test_sources_list_in_response(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer", [])
        resp = client.post("/api/query", json={"query": "test"})
        assert resp.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200

    def test_total_courses_matches_sample_data(self, client):
        resp = client.get("/api/courses")
        assert resp.json()["total_courses"] == len(SAMPLE_COURSES)

    def test_course_titles_match_sample_data(self, client):
        resp = client.get("/api/courses")
        assert resp.json()["course_titles"] == SAMPLE_COURSES

    def test_calls_get_course_analytics(self, client, mock_rag_system):
        client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_returns_500_when_analytics_raises(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Chroma error")
        resp = client.get("/api/courses")
        assert resp.status_code == 500

    def test_500_detail_propagated(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Chroma error")
        resp = client.get("/api/courses")
        assert "Chroma error" in resp.json()["detail"]

    def test_empty_course_list(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        resp = client.get("/api/courses")
        assert resp.json()["total_courses"] == 0
        assert resp.json()["course_titles"] == []

    def test_response_schema_has_required_fields(self, client):
        resp = client.get("/api/courses")
        data = resp.json()
        assert "total_courses" in data
        assert "course_titles" in data


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestClearSessionEndpoint:
    def test_returns_200(self, client):
        resp = client.delete("/api/session/my-session")
        assert resp.status_code == 200

    def test_response_status_is_cleared(self, client):
        resp = client.delete("/api/session/my-session")
        assert resp.json() == {"status": "cleared"}

    def test_calls_clear_session_with_correct_id(self, client, mock_rag_system):
        client.delete("/api/session/sess-99")
        mock_rag_system.session_manager.clear_session.assert_called_once_with("sess-99")

    def test_different_session_ids_are_forwarded(self, client, mock_rag_system):
        client.delete("/api/session/abc")
        client.delete("/api/session/xyz")
        calls = [c[0][0] for c in mock_rag_system.session_manager.clear_session.call_args_list]
        assert calls == ["abc", "xyz"]
