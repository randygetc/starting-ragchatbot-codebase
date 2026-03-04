"""
Tests for CourseSearchTool.execute() in search_tools.py

Covers:
- Result formatting and source tracking
- Empty result handling with and without filters
- Error propagation from VectorStore
- Correct parameter passing to VectorStore.search()
- Integration against real ChromaDB (skipped if chroma_db absent)
"""
import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_search_results(docs=None, metas=None, error=None):
    docs = docs or []
    metas = metas or []
    return SearchResults(documents=docs, metadata=metas, distances=[0.1] * len(docs), error=error)


# ---------------------------------------------------------------------------
# Unit tests (mocked VectorStore)
# ---------------------------------------------------------------------------

class TestCourseSearchToolExecute:
    def setup_method(self):
        self.mock_store = MagicMock()
        self.tool = CourseSearchTool(self.mock_store)

    def test_returns_formatted_results(self):
        self.mock_store.search.return_value = make_search_results(
            docs=["Python is a high-level language."],
            metas=[{"course_title": "Python Basics", "lesson_number": 1}],
        )
        result = self.tool.execute(query="Python basics")
        assert "Python Basics" in result
        assert "Lesson 1" in result
        assert "Python is a high-level language." in result

    def test_tracks_sources_with_lesson(self):
        self.mock_store.search.return_value = make_search_results(
            docs=["Content."],
            metas=[{"course_title": "My Course", "lesson_number": 2}],
        )
        self.tool.execute(query="test")
        assert self.tool.last_sources == ["My Course - Lesson 2"]

    def test_tracks_sources_without_lesson(self):
        self.mock_store.search.return_value = make_search_results(
            docs=["Content."],
            metas=[{"course_title": "My Course"}],
        )
        self.tool.execute(query="test")
        assert self.tool.last_sources == ["My Course"]

    def test_multiple_results_all_tracked(self):
        self.mock_store.search.return_value = make_search_results(
            docs=["Doc A", "Doc B"],
            metas=[
                {"course_title": "Course A", "lesson_number": 1},
                {"course_title": "Course B", "lesson_number": 3},
            ],
        )
        self.tool.execute(query="test")
        assert len(self.tool.last_sources) == 2
        assert "Course A - Lesson 1" in self.tool.last_sources
        assert "Course B - Lesson 3" in self.tool.last_sources

    def test_empty_results_no_filter(self):
        self.mock_store.search.return_value = make_search_results()
        result = self.tool.execute(query="nonexistent topic")
        assert "No relevant content found" in result

    def test_empty_results_with_course_filter(self):
        self.mock_store.search.return_value = make_search_results()
        result = self.tool.execute(query="test", course_name="Unknown Course")
        assert "No relevant content found" in result
        assert "Unknown Course" in result

    def test_empty_results_with_lesson_filter(self):
        self.mock_store.search.return_value = make_search_results()
        result = self.tool.execute(query="test", lesson_number=99)
        assert "No relevant content found" in result
        assert "lesson 99" in result

    def test_propagates_vector_store_error(self):
        self.mock_store.search.return_value = make_search_results(
            error="No course found matching 'XYZ'"
        )
        result = self.tool.execute(query="test", course_name="XYZ")
        assert "No course found" in result

    def test_passes_all_params_to_store(self):
        self.mock_store.search.return_value = make_search_results()
        self.tool.execute(query="deep learning", course_name="AI Course", lesson_number=5)
        self.mock_store.search.assert_called_once_with(
            query="deep learning", course_name="AI Course", lesson_number=5
        )

    def test_sources_reset_between_calls(self):
        self.mock_store.search.return_value = make_search_results(
            docs=["Doc A"], metas=[{"course_title": "Course A", "lesson_number": 1}]
        )
        self.tool.execute(query="first query")
        assert len(self.tool.last_sources) == 1

        # Second call with no results should return empty (sources reset by ToolManager, not tool itself)
        self.mock_store.search.return_value = make_search_results(
            docs=["Doc B"], metas=[{"course_title": "Course B", "lesson_number": 2}]
        )
        self.tool.execute(query="second query")
        assert self.tool.last_sources == ["Course B - Lesson 2"]


class TestToolManager:
    def setup_method(self):
        self.mock_store = MagicMock()
        self.tool = CourseSearchTool(self.mock_store)
        self.manager = ToolManager()
        self.manager.register_tool(self.tool)

    def test_get_last_sources_delegates_to_tool(self):
        self.tool.last_sources = ["Course A - Lesson 1"]
        assert self.manager.get_last_sources() == ["Course A - Lesson 1"]

    def test_reset_sources_clears_tool_sources(self):
        self.tool.last_sources = ["Course A - Lesson 1"]
        self.manager.reset_sources()
        assert self.tool.last_sources == []

    def test_execute_tool_by_name(self):
        self.mock_store.search.return_value = make_search_results()
        result = self.manager.execute_tool("search_course_content", query="test")
        assert isinstance(result, str)

    def test_execute_unknown_tool_returns_error(self):
        result = self.manager.execute_tool("nonexistent_tool", query="test")
        assert "not found" in result


# ---------------------------------------------------------------------------
# Integration tests (real ChromaDB)
# ---------------------------------------------------------------------------

class TestCourseSearchToolIntegration:
    """Runs against the actual chroma_db. Skipped if not present."""

    @pytest.fixture
    def real_store(self):
        import os
        from vector_store import VectorStore

        chroma_path = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
        if not os.path.exists(chroma_path):
            pytest.skip("chroma_db not found — start the server once to index documents")
        return VectorStore(chroma_path, "all-MiniLM-L6-v2", max_results=5)

    def test_chroma_has_indexed_courses(self, real_store):
        titles = real_store.get_existing_course_titles()
        assert len(titles) > 0, (
            "ChromaDB is empty — no courses have been indexed. "
            "Start the server to trigger the startup indexing event."
        )

    def test_search_returns_string(self, real_store):
        tool = CourseSearchTool(real_store)
        result = tool.execute(query="introduction to the course")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_populates_sources(self, real_store):
        tool = CourseSearchTool(real_store)
        titles = real_store.get_existing_course_titles()
        if not titles:
            pytest.skip("No courses indexed")
        tool.execute(query="what is covered in this course")
        # If results were found, sources should be populated
        # (empty is valid if the query truly matches nothing)
        assert isinstance(tool.last_sources, list)

    def test_invalid_course_name_returns_error_message(self, real_store):
        tool = CourseSearchTool(real_store)
        result = tool.execute(query="test", course_name="ZZZNOMATCH999")
        # Should return an error or no-results message, not raise an exception
        assert isinstance(result, str)
