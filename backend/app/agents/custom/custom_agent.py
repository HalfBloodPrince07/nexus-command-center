"""CustomAgent implementation for user-defined specialist agents."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from backend.app.agents._lm_studio import complete_chat
from backend.core.database import database
from backend.mcp.tools import TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

# State-mutating tools that persist data
STATE_MUTATING_TOOLS = {"save_memory", "save_research_report"}


class CustomAgentRunError(Exception):
    """Raised when a custom agent run fails."""


class CustomAgent:
    """User-defined agent with custom system prompt and restricted tool access."""

    def __init__(self, agent_id: str, user_id: str) -> None:
        """Initialize agent with config from DB.
        
        Args:
            agent_id: UUID of the custom agent
            user_id: User who owns this agent
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self.config: dict[str, Any] | None = None
        self.allowed_tools: set[str] = set()
        self.system_prompt_snapshot: str = ""
        self.name: str = ""
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        """Lazy-load agent config from database."""
        if self._loaded:
            return

        config = await database.get_custom_agent(self.agent_id, self.user_id)
        if not config:
            raise ValueError(f"Custom agent {self.agent_id} not found for user {self.user_id}")

        self.config = config
        self.name = config["name"]
        self.system_prompt_snapshot = config["system_prompt"]
        self.allowed_tools = set(config.get("allowed_tools", []))
        self._loaded = True

    async def _check_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is in the agent's whitelist."""
        await self._ensure_loaded()
        return tool_name in self.allowed_tools

    def _get_tool_metadata(self) -> list[dict[str, Any]]:
        """Get metadata for allowed tools."""
        return [
            {
                "name": name,
                "description": tool.__doc__ or "",
                "mutates_state": name in STATE_MUTATING_TOOLS,
            }
            for name, tool in TOOL_FUNCTIONS.items()
            if name in self.allowed_tools
        ]

    async def _execute_tool(self, tool_name: str, tool_params: dict[str, Any]) -> dict[str, Any]:
        """Execute a single tool with error handling and input validation.
        
        Args:
            tool_name: Name of the MCP tool to call
            tool_params: Parameters for the tool call
            
        Returns:
            Dict with tool result or error
        """
        if not await self._check_tool_allowed(tool_name):
            return {"error": f"Tool '{tool_name}' not in agent's allowed tools whitelist"}

        tool = TOOL_FUNCTIONS.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found in registry"}

        try:
            # Execute tool with timeout
            result = await tool(**tool_params)
            if hasattr(result, "model_dump"):
                return result.model_dump()
            return {"result": result}
        except Exception as exc:
            logger.error("Tool execution failed: %s(%s) - %s", tool_name, tool_params, exc)
            return {"error": f"Tool '{tool_name}' failed: {str(exc)}"}

    async def run(
        self,
        prompt: str,
        *,
        test_mode: bool = False,
        enable_state_mutation: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the custom agent with a user prompt.
        
        Args:
            prompt: User's natural language prompt
            test_mode: If True, dry-run without executing tools or persisting state
            enable_state_mutation: If False, block state-mutating tools
            
        Yields:
            Streaming events: "tool_call", "tool_result", "chunk", "end"
        """
        await self._ensure_loaded()

        invocation_id: str | None = None
        if not test_mode:
            invocation_id = await database.add_custom_agent_invocation(
                agent_id=self.agent_id,
                user_id=self.user_id,
                prompt=prompt,
                system_prompt_snapshot=self.system_prompt_snapshot,
                started_at=datetime.now(timezone.utc),
                tools_used=json.dumps(list(self.allowed_tools)),
                tool_params=json.dumps({}),
                response=None,
                completed_at=None,
                succeeded=None,
            )

        tool_results: list[dict[str, Any]] = []
        succeeded = False

        try:
            # Build messages for LLM
            messages = [{"role": "system", "content": self.system_prompt_snapshot}]
            messages.append({"role": "user", "content": prompt})

            # Get allowed tools metadata
            tools_metadata = self._get_tool_metadata()
            if tools_metadata:
                messages.append({"role": "system", "content": f"## Available Tools\nYou may use these tools:\n{json.dumps(tools_metadata, indent=2)}"})

            if test_mode:
                messages.append({"role": "system", "content": "### TEST MODE\n- Do NOT execute any tools\n- State-mutating functions are DISABLED\n- Show what WOULD be called\n"})
            elif not enable_state_mutation:
                mutating_tools = [t["name"] for t in tools_metadata if t.get("mutates_state")]
                if mutating_tools:
                    messages.append({
                        "role": "system",
                        "content": f"### STATE-MUTATION LOCKED\nThese tools require explicit opt-in: {', '.join(mutating_tools)}\nThey will be BLOCKED unless enable_state_mutation=True.\n",
                    })

            # Stream response from LLM
            full_response = ""
            async for chunk in complete_chat(messages, model="llama3.1", temperature=self.config["temperature"]):
                full_response += chunk.get("content", "")
                yield {"type": "chunk", "content": chunk.get("content", "")}

            # Parse tool calls from response (simple regex-based for now)
            tool_calls = await self._extract_tool_calls(full_response)

            # Execute allowed tools
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_params = tool_call.get("parameters", {})

                yield {"type": "tool_call", "tool": tool_name, "params": tool_params}

                # Check for state-mutating tools
                if tool_name in STATE_MUTATING_TOOLS and not enable_state_mutation:
                    result = {"error": f"State-mutating tool '{tool_name}' blocked. Enable with enable_state_mutation=True."}
                elif test_mode:
                    result = {"test_mode": True, "would_call": {"tool": tool_name, "params": tool_params}}
                else:
                    result = await self._execute_tool(tool_name, tool_params)

                tool_results.append({"tool": tool_name, "result": result})
                yield {"type": "tool_result", "tool": tool_name, "result": result}

            succeeded = True

        except Exception as exc:
            logger.error("Custom agent run failed: %s", exc, exc_info=True)
            yield {"type": "error", "error": str(exc)}
            succeeded = False
            raise CustomAgentRunError from exc

        finally:
            # Update invocation record
            if invocation_id:
                await database.add_custom_agent_invocation(
                    id=invocation_id,
                    response=full_response,
                    completed_at=datetime.now(timezone.utc),
                    succeeded=succeeded,
                )

            yield {"type": "end", "success": succeeded}

    async def _extract_tool_calls(self, response: str) -> list[dict[str, Any]]:
        """Extract tool calls from LLM response.
        
        Simple regex-based parser. In production, use structured outputs.
        Expected format:
        ```json
        {"tool": "save_memory", "parameters": {"fact": "...", "category": "...", "importance": 8}}
        ```
        """
        import re

        pattern = r"```json\s*({\s*"tool":\s*"(\w+)",\s*"parameters":\s*({.*?})\s*})\s*```"
        matches = re.findall(pattern, response, re.DOTALL)

        tool_calls = []
        for _, tool_name, params_str in matches[:5]:  # Limit to 5 tool calls max
            try:
                params = json.loads(params_str)
                if await self._check_tool_allowed(tool_name):
                    tool_calls.append({"name": tool_name, "parameters": params})
            except (json.JSONDecodeError, ValueError):
                logger.warning("Invalid tool call in response: %s", params_str[:100])

        return tool_calls


async def run_custom_agent(
    agent_id: str,
    user_id: str,
    prompt: str,
    *,
    test_mode: bool = False,
    enable_state_mutation: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Convenience wrapper: instantiate and run a custom agent.

    Args:
        agent_id: ID of the custom agent to run
        user_id: User who owns this agent
        prompt: User's natural language prompt
        test_mode: Dry-run mode without tool execution
        enable_state_mutation: Enable state-mutating tools

    Yields:
        Streaming events from agent run
    """
    agent = CustomAgent(agent_id=agent_id, user_id=user_id)
    async for event in agent.run(
        prompt=prompt,
        test_mode=test_mode,
        enable_state_mutation=enable_state_mutation,
    ):
        yield event
