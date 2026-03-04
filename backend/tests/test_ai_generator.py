"""
Tests for AIGenerator in ai_generator.py

Covers:
- Direct (no-tool) response path
- Single tool-use round (early termination)
- Two sequential tool-use rounds
- Final fallback call excludes tools after rounds are exhausted
- Tool execution errors don't raise; error text is embedded in tool_result
- Conversation history is injected into system prompt
- Model name is a known valid Anthropic model
"""
import pytest
from unittest.mock import MagicMock, patch
from ai_generator import AIGenerator, MAX_TOOL_ROUNDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KNOWN_VALID_MODELS = {
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-sonnet-4-20250514",
}

TOOL_DEFINITION = [{"name": "search_course_content"}]


def make_generator():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="claude-test")
    return gen


def make_end_turn_response(text="Direct answer"):
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [MagicMock(text=text)]
    return resp


def make_tool_use_response(tool_name="search_course_content", tool_id="tool_001", tool_input=None):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = tool_id
    tool_block.input = tool_input or {"query": "test query"}

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [tool_block]
    return resp


def make_tool_manager(return_value="Search results here"):
    m = MagicMock()
    m.execute_tool.return_value = return_value
    return m


# ---------------------------------------------------------------------------
# Tests: direct response (no tool use)
# ---------------------------------------------------------------------------

class TestDirectResponse:
    def setup_method(self):
        self.gen = make_generator()

    def test_returns_text_on_end_turn(self):
        self.gen.client.messages.create.return_value = make_end_turn_response("Hello world")
        result = self.gen.generate_response(query="What is Python?")
        assert result == "Hello world"

    def test_single_api_call_when_no_tool_use(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(query="What is Python?")
        assert self.gen.client.messages.create.call_count == 1

    def test_user_query_included_in_messages(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(query="What is recursion?")
        call_kwargs = self.gen.client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        assert any(
            m["role"] == "user" and "What is recursion?" in m["content"]
            for m in messages
        )

    def test_system_prompt_contains_base_instructions(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(query="test")
        call_kwargs = self.gen.client.messages.create.call_args[1]
        assert "course materials" in call_kwargs["system"].lower()

    def test_conversation_history_appended_to_system_prompt(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(query="test", conversation_history="User: hi\nAssistant: hello")
        call_kwargs = self.gen.client.messages.create.call_args[1]
        assert "User: hi" in call_kwargs["system"]
        assert "Assistant: hello" in call_kwargs["system"]

    def test_no_history_uses_base_system_prompt_only(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(query="test", conversation_history=None)
        call_kwargs = self.gen.client.messages.create.call_args[1]
        assert "Previous conversation:" not in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Tests: single tool-use round (early termination on round 1)
# ---------------------------------------------------------------------------

class TestToolUseLoop:
    def setup_method(self):
        self.gen = make_generator()
        self.tool_manager = make_tool_manager()

    def test_tool_manager_called_on_tool_use(self):
        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "Python basics"}),
            make_end_turn_response("Final answer"),
        ]
        self.gen.generate_response(
            query="What does Lesson 1 cover?",
            tools=TOOL_DEFINITION,
            tool_manager=self.tool_manager,
        )
        self.tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="Python basics"
        )

    def test_returns_final_answer_after_tool_use(self):
        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response("Answer synthesized from search"),
        ]
        result = self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert result == "Answer synthesized from search"

    def test_two_api_calls_when_single_tool_round(self):
        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response(),
        ]
        self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert self.gen.client.messages.create.call_count == 2

    def test_intermediate_calls_include_tools(self):
        """Round 1 call must include tools so Claude can search again if needed."""
        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response(),
        ]
        self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        first_call_kwargs = self.gen.client.messages.create.call_args_list[0][1]
        assert "tools" in first_call_kwargs

    def test_tool_result_message_structure(self):
        """The tool result sent back to Claude must match the Anthropic API format."""
        tool_use_resp = make_tool_use_response(tool_id="tool_abc", tool_input={"query": "test"})
        self.gen.client.messages.create.side_effect = [
            tool_use_resp,
            make_end_turn_response(),
        ]
        self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        second_call_messages = self.gen.client.messages.create.call_args_list[1][1]["messages"]
        tool_result_msg = next(
            m for m in reversed(second_call_messages) if m["role"] == "user"
        )
        result_block = tool_result_msg["content"][0]
        assert result_block["type"] == "tool_result"
        assert result_block["tool_use_id"] == "tool_abc"
        assert "Search results" in result_block["content"]

    def test_assistant_tool_use_response_included_in_messages(self):
        """Claude's tool_use response must be included as an assistant message."""
        first_resp = make_tool_use_response()
        self.gen.client.messages.create.side_effect = [first_resp, make_end_turn_response()]
        self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        second_call_messages = self.gen.client.messages.create.call_args_list[1][1]["messages"]
        assistant_messages = [m for m in second_call_messages if m["role"] == "assistant"]
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] == first_resp.content

    def test_tool_manager_not_called_without_tool_use(self):
        self.gen.client.messages.create.return_value = make_end_turn_response()
        self.gen.generate_response(
            query="What is 2+2?", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        self.tool_manager.execute_tool.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: two sequential tool-use rounds
# ---------------------------------------------------------------------------

class TestTwoRoundToolUse:
    """
    Tests for the sequential two-round case where Claude makes a tool call
    on both round 1 and round 2, then gives a final answer.

    API call sequence: tool_use_1 → tool_use_2 → end_turn (3 total)
    """

    def setup_method(self):
        self.gen = make_generator()
        self.tool_manager = make_tool_manager()
        self.two_round_responses = [
            make_tool_use_response(tool_id="tool_001", tool_input={"query": "first search"}),
            make_tool_use_response(tool_id="tool_002", tool_input={"query": "second search"}),
            make_end_turn_response("Final synthesized answer"),
        ]

    def test_two_rounds_makes_three_api_calls(self):
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert self.gen.client.messages.create.call_count == 3

    def test_tool_manager_called_twice(self):
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert self.tool_manager.execute_tool.call_count == 2

    def test_final_call_excludes_tools(self):
        """After both rounds are used, the final synthesizing call must not include tools."""
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        third_call_kwargs = self.gen.client.messages.create.call_args_list[2][1]
        assert "tools" not in third_call_kwargs

    def test_intermediate_round_includes_tools(self):
        """Round 2 call must still include tools so Claude can stop early if it wants."""
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        second_call_kwargs = self.gen.client.messages.create.call_args_list[1][1]
        assert "tools" in second_call_kwargs

    def test_both_tool_results_in_final_messages(self):
        """The final API call must contain both rounds' tool results in message history."""
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        final_messages = self.gen.client.messages.create.call_args_list[2][1]["messages"]
        tool_result_turns = [
            m for m in final_messages
            if m["role"] == "user" and isinstance(m["content"], list)
            and any(b.get("type") == "tool_result" for b in m["content"])
        ]
        assert len(tool_result_turns) == 2

    def test_stops_early_on_end_turn_during_round_two(self):
        """If Claude stops during round 2, no extra fallback call is made."""
        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response("Answer after one search"),
        ]
        result = self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert self.gen.client.messages.create.call_count == 2
        assert result == "Answer after one search"

    def test_returns_text_from_final_response(self):
        self.gen.client.messages.create.side_effect = self.two_round_responses
        result = self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        assert result == "Final synthesized answer"

    def test_second_round_uses_correct_tool_input(self):
        """Round 2 must execute the tool with the inputs from the second tool_use block."""
        self.gen.client.messages.create.side_effect = self.two_round_responses
        self.gen.generate_response(
            query="Compare courses", tools=TOOL_DEFINITION, tool_manager=self.tool_manager
        )
        calls = self.tool_manager.execute_tool.call_args_list
        assert calls[0][1] == {"query": "first search"}
        assert calls[1][1] == {"query": "second search"}

    def test_max_tool_rounds_constant_is_two(self):
        assert MAX_TOOL_ROUNDS == 2


# ---------------------------------------------------------------------------
# Tests: tool execution errors
# ---------------------------------------------------------------------------

class TestToolExecutionError:
    def setup_method(self):
        self.gen = make_generator()

    def test_tool_error_does_not_raise(self):
        """An exception from execute_tool must not propagate out of generate_response."""
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("DB connection failed")

        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response("I couldn't retrieve that info"),
        ]
        result = self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=tool_manager
        )
        assert isinstance(result, str)

    def test_tool_error_embedded_in_tool_result(self):
        """The error message must be sent back to Claude as the tool_result content."""
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("DB connection failed")

        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(tool_id="err_tool"),
            make_end_turn_response(),
        ]
        self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=tool_manager
        )
        second_call_messages = self.gen.client.messages.create.call_args_list[1][1]["messages"]
        tool_result_turn = next(
            m for m in reversed(second_call_messages) if m["role"] == "user"
        )
        result_content = tool_result_turn["content"][0]["content"]
        assert "error" in result_content.lower()

    def test_loop_continues_after_tool_error(self):
        """After a failed tool, the API must still be called to get Claude's answer."""
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("timeout")

        self.gen.client.messages.create.side_effect = [
            make_tool_use_response(),
            make_end_turn_response("Sorry, search failed"),
        ]
        result = self.gen.generate_response(
            query="test", tools=TOOL_DEFINITION, tool_manager=tool_manager
        )
        assert self.gen.client.messages.create.call_count == 2
        assert result == "Sorry, search failed"


# ---------------------------------------------------------------------------
# Configuration / model name validation
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_configured_model_is_a_known_valid_model(self):
        from config import config
        assert config.ANTHROPIC_MODEL in KNOWN_VALID_MODELS, (
            f"Model '{config.ANTHROPIC_MODEL}' is not in the known-valid model list. "
            f"Valid models: {KNOWN_VALID_MODELS}. "
            "Update ANTHROPIC_MODEL in backend/config.py."
        )

    def test_api_key_is_not_placeholder(self):
        from config import config
        assert config.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY is not set in .env"
        assert config.ANTHROPIC_API_KEY != "your-anthropic-api-key-here", (
            "ANTHROPIC_API_KEY is still the placeholder value. Set a real key in .env"
        )
        assert config.ANTHROPIC_API_KEY.startswith("sk-ant-"), (
            f"ANTHROPIC_API_KEY doesn't look like a valid Anthropic key: '{config.ANTHROPIC_API_KEY[:10]}...'"
        )
