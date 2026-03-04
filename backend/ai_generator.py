import anthropic
from typing import List, Optional, Dict, Any

MAX_TOOL_ROUNDS = 2

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- You may search **up to 2 times per query** when a follow-up search with a more specific query would meaningfully improve your answer
- Each search should use a distinct query — do not repeat the same search twice
- Synthesize all search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional sequential tool usage and conversation context.

        Supports up to MAX_TOOL_ROUNDS sequential tool-call rounds. Each round sees the
        full accumulated message history so Claude can reason about prior results before
        deciding whether to search again.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        api_params = {**self.base_params, "system": system_content}
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.messages.create(**api_params, messages=messages)

            # Termination: Claude answered directly or no tool executor available
            if response.stop_reason != "tool_use" or not tool_manager:
                return response.content[0].text

            # Accumulate assistant turn and tool results into message history
            messages.append({"role": "assistant", "content": response.content})
            tool_results = self._execute_tools(response, tool_manager)
            messages.append({"role": "user", "content": tool_results})

        # All rounds used — final call WITHOUT tools to get Claude's synthesis
        final_params = {**self.base_params, "system": system_content, "messages": messages}
        return self.client.messages.create(**final_params).content[0].text

    def _execute_tools(self, response, tool_manager) -> List[Dict]:
        """
        Pure tool executor. Executes all tool_use blocks in a response.

        Returns a list of tool_result dicts in Anthropic API format. Never calls the API.
        Errors from tool execution are caught and embedded in the result content so the
        loop can continue and Claude can acknowledge the failure gracefully.
        """
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                content = tool_manager.execute_tool(block.name, **block.input)
            except Exception as exc:
                content = f"Tool execution error: {exc}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        return tool_results
