"""
Tests for RAGSystem.query() in rag_system.py

Covers:
- Answer and sources are returned correctly
- Session history is fetched and saved
- Tools and tool_manager are passed to AIGenerator
- Sources are reset after each query
- Session is skipped when session_id is None
- Integration smoke test against real components (skipped if chroma_db absent)
"""
import pytest
from unittest.mock import MagicMock, patch
from rag_system import RAGSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rag_system():
    """Build a RAGSystem with all external dependencies mocked."""
    with patch("rag_system.DocumentProcessor"), \
         patch("rag_system.VectorStore"), \
         patch("rag_system.AIGenerator"), \
         patch("rag_system.SessionManager"), \
         patch("rag_system.ToolManager"), \
         patch("rag_system.CourseSearchTool"):
        mock_config = MagicMock()
        rag = RAGSystem(mock_config)

    rag.ai_generator.generate_response.return_value = "Test answer"
    rag.tool_manager.get_last_sources.return_value = []
    rag.tool_manager.get_tool_definitions.return_value = [{"name": "search_course_content"}]
    rag.session_manager.get_conversation_history.return_value = None
    return rag


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestRAGSystemQuery:
    def setup_method(self):
        self.rag = make_rag_system()

    # --- Return values ---

    def test_returns_answer_string(self):
        answer, _ = self.rag.query("What is Python?", session_id="s1")
        assert answer == "Test answer"

    def test_returns_sources_list(self):
        self.rag.tool_manager.get_last_sources.return_value = ["Course A - Lesson 1"]
        _, sources = self.rag.query("What is Python?", session_id="s1")
        assert sources == ["Course A - Lesson 1"]

    def test_returns_empty_sources_when_no_search(self):
        self.rag.tool_manager.get_last_sources.return_value = []
        _, sources = self.rag.query("What is 2+2?", session_id="s1")
        assert sources == []

    # --- Session management ---

    def test_fetches_conversation_history_for_session(self):
        self.rag.query("test", session_id="s1")
        self.rag.session_manager.get_conversation_history.assert_called_once_with("s1")

    def test_history_passed_to_ai_generator(self):
        self.rag.session_manager.get_conversation_history.return_value = "User: hi\nAssistant: hello"
        self.rag.query("test", session_id="s1")
        call_kwargs = self.rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == "User: hi\nAssistant: hello"

    def test_saves_exchange_to_session_after_query(self):
        self.rag.ai_generator.generate_response.return_value = "My answer"
        self.rag.query("My question", session_id="s1")
        self.rag.session_manager.add_exchange.assert_called_once_with(
            "s1", "My question", "My answer"
        )

    def test_no_session_skips_history_fetch(self):
        self.rag.query("test", session_id=None)
        self.rag.session_manager.get_conversation_history.assert_not_called()

    def test_no_session_skips_save_exchange(self):
        self.rag.query("test", session_id=None)
        self.rag.session_manager.add_exchange.assert_not_called()

    # --- Tool wiring ---

    def test_tools_passed_to_ai_generator(self):
        self.rag.query("test", session_id="s1")
        call_kwargs = self.rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["tools"] == [{"name": "search_course_content"}]

    def test_tool_manager_passed_to_ai_generator(self):
        self.rag.query("test", session_id="s1")
        call_kwargs = self.rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["tool_manager"] is self.rag.tool_manager

    # --- Source lifecycle ---

    def test_sources_reset_after_each_query(self):
        self.rag.query("test", session_id="s1")
        self.rag.tool_manager.reset_sources.assert_called_once()

    def test_sources_reset_even_when_sources_empty(self):
        self.rag.tool_manager.get_last_sources.return_value = []
        self.rag.query("test", session_id="s1")
        self.rag.tool_manager.reset_sources.assert_called_once()

    # --- Query wrapping ---

    def test_query_is_wrapped_in_prompt(self):
        """RAGSystem wraps the raw query before sending to AIGenerator."""
        self.rag.query("How does recursion work?", session_id="s1")
        call_kwargs = self.rag.ai_generator.generate_response.call_args[1]
        sent_query = call_kwargs["query"]
        assert "How does recursion work?" in sent_query


# ---------------------------------------------------------------------------
# Integration smoke test (real ChromaDB + real Anthropic skipped by default)
# ---------------------------------------------------------------------------

class TestRAGSystemIntegration:
    """
    End-to-end test against real ChromaDB.
    Skipped if chroma_db is absent.
    Uses real Anthropic API — requires valid ANTHROPIC_API_KEY in .env.
    """

    @pytest.fixture
    def real_rag(self):
        import os
        chroma_path = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
        if not os.path.exists(chroma_path):
            pytest.skip("chroma_db not found — start the server once first")

        from config import config
        if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "your-anthropic-api-key-here":
            pytest.skip("No valid ANTHROPIC_API_KEY in .env")

        return RAGSystem(config)

    @pytest.mark.integration
    def test_general_knowledge_query_returns_string(self, real_rag):
        """A factual question that doesn't need RAG search should still return text."""
        answer, sources = real_rag.query("What does RAG stand for?", session_id="test_session")
        assert isinstance(answer, str)
        assert len(answer) > 0

    @pytest.mark.integration
    def test_course_query_returns_answer_and_sources(self, real_rag):
        """A course-specific question should trigger a search and return sources."""
        titles = real_rag.vector_store.get_existing_course_titles()
        if not titles:
            pytest.skip("No courses indexed in ChromaDB")

        answer, sources = real_rag.query(
            f"What is covered in the course '{titles[0]}'?",
            session_id="test_session_2"
        )
        assert isinstance(answer, str)
        assert len(answer) > 0
        # Sources may or may not be populated depending on Claude's decision to search

    @pytest.mark.integration
    def test_session_history_accumulates(self, real_rag):
        """Subsequent queries should have access to prior conversation context."""
        session_id = "history_test_session"
        real_rag.query("Hello, who are you?", session_id=session_id)
        history = real_rag.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "Hello" in history
