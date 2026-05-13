import asyncio
import logging
from typing import AsyncGenerator, List, TypedDict, Annotated, cast

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from backend.config import settings
from backend.core.resilience import degraded_event

# Configure logging
logger = logging.getLogger(__name__)

# Event tracking for agent network visualization
try:
    from backend.core.event_bus import publish_agent_message

    event_tracking = True
except ImportError:
    event_tracking = False
    logger.warning("Event bus not available. Agent communications will not be tracked.")


class NexusConnectionError(Exception):
    """Custom error for connection issues to external services like LM Studio."""

    pass


# --- Stub/Optional Imports ---
try:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url="http://localhost:1234/v1",
        api_key="lm-studio",  # Required but not used by LM Studio
        model=settings.SUPERVISOR_MODEL,
        streaming=True,
        temperature=0.7,
    )
except ImportError:
    llm = None
    logger.error("Could not import langchain_openai. Please install it.")
except Exception as e:
    llm = None
    logger.error("Failed to initialize ChatOpenAI client for LM Studio: %s", e)

try:
    from backend.core import database
except ImportError:
    database = None
    logger.warning(
        "Database module not found. Supervisor will operate without history."
    )

try:
    from backend.core import personality
except ImportError:
    personality = None
    logger.warning(
        "Personality module not found. Supervisor will use a default personality."
    )


# --- LangGraph State ---
class SupervisorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_id: str
    is_streaming: bool


# --- LangGraph Node ---
async def supervisor_node(state: SupervisorState) -> SupervisorState:
    """The primary logic node for the supervisor agent."""
    if not llm:
        raise NexusConnectionError("Supervisor LLM client is not initialized.")

    # Get the active personality prompt
    personality_prompt = (
        personality.get_active_personality()
        if personality
        else "You are a helpful AI assistant."
    )

    current_messages = state["messages"]

    # Prepend personality to the message history if it's not already there
    if not current_messages or not isinstance(current_messages[0], SystemMessage):
        messages_with_personality = [
            SystemMessage(content=personality_prompt)
        ] + current_messages
    else:
        messages_with_personality = current_messages

    # Stream the response from the LLM
    response_stream = llm.astream(messages_with_personality)

    # Aggregate the full response to append to the state
    full_response_content = ""
    async for chunk in response_stream:
        full_response_content += cast(str, chunk.content)

    # The state is primarily for graph flow; the actual streaming happens in stream_response
    # Here we just formally conclude the graph turn by adding the final AIMessage
    return {"messages": [AIMessage(content=full_response_content)]}


# --- Graph Definition ---
graph_builder = StateGraph(SupervisorState)
graph_builder.add_node("supervisor", supervisor_node)
graph_builder.set_entry_point("supervisor")
graph_builder.add_edge("supervisor", END)

supervisor_graph = graph_builder.compile()


# --- Public Interface ---
async def stream_response(
    user_message: str, conversation_id: str
) -> AsyncGenerator[str, None]:
    """
    Loads history, streams a response from the LLM token-by-token, and saves the full exchange.
    """
    if not llm:
        yield "Error: Supervisor LLM is not configured or available."
        return

    # 1. Load conversation history
    if event_tracking:
        # Track that supervisor received message from user
        try:
            from backend.core.event_bus import publish_agent_message

            publish_agent_message(
                from_agent="user",
                to_agent="supervisor",
                message_type="message_received",
                payload={"conversation_id": conversation_id},
            )
        except Exception as e:
            logger.debug("Failed to publish event: %s", e)

    history_messages: List[BaseMessage] = []
    if database:
        try:
            history = await database.get_conversation_history(conversation_id, limit=20)
            for msg in history:
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    history_messages.append(AIMessage(content=msg["content"]))
        except Exception as e:
            logger.error(
                "Failed to load conversation history for %s: %s", conversation_id, e
            )
            # Non-fatal, continue without history

    # 2. Append the new user message
    history_messages.append(HumanMessage(content=user_message))

    # 3. Add the personality prompt
    try:
        personality_prompt = personality.get_system_prompt(agent_id="supervisor")
    except Exception as e:
        logger.error("Could not load personality prompt in stream: %s", e)
        personality_prompt = "You are a helpful assistant."
    messages_to_send = [SystemMessage(content=personality_prompt)] + history_messages

    # 4. Stream the response directly from the LLM client
    full_ai_response = ""
    try:
        async for chunk in llm.astream(messages_to_send):
            token = cast(str, chunk.content)
            if token:
                full_ai_response += token
                yield token
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error(
            "Error streaming response from LLM for conversation %s: %s",
            conversation_id,
            e,
        )
        yield degraded_event(
            "supervisor", "llm_unavailable", "Supervisor could not reach LM Studio."
        )
        yield "I can't reach the local model right now — start LM Studio and try again."
        return
    except Exception as e:
        logger.error(
            "Error streaming response from LLM for conversation %s: %s",
            conversation_id,
            e,
        )
        yield degraded_event("supervisor", "response_failed", str(e))
        yield "I can't complete that response right now. Please try again."
        return

    # 5. Save the complete user message and AI response to the database
    if database and full_ai_response:
        try:
            await database.save_message(conversation_id, "user", user_message)
            await database.save_message(
                conversation_id, "assistant", full_ai_response, agent_id="supervisor"
            )
        except (OSError, RuntimeError) as e:
            logger.error(
                "Failed to save conversation exchange for %s: %s", conversation_id, e
            )
            yield degraded_event(
                "supervisor",
                "conversation_persist_failed",
                "Could not save this exchange to disk.",
            )
            # This is non-fatal to the user, but should be monitored


async def check_lm_studio_connection() -> bool:
    """Performs a lightweight check to see if LM Studio is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:1234/v1/models")
            return response.status_code == 200
    except httpx.RequestError:
        return False
