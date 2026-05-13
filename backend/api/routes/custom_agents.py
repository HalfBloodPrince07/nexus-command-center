"""API routes for custom agent management and execution."""

from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from backend.app.agents.custom import CustomAgent
from backend.core.database import database
from backend.core.safety.prompt_validator import validate_system_prompt

router = APIRouter(prefix="/agents/custom", tags=["custom_agents"])

# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class CreateCustomAgentRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=60, pattern=r"^[a-z0-9\-_]+$")
    display_name: str | None = Field(None, max_length=100)
    tagline: str | None = Field(None, max_length=200)
    system_prompt: str = Field(..., min_length=10, max_length=5000)
    allowed_tools: list[str] = Field(default_factory=list, max_length=6)
    parent_cluster: str | None = Field(
        None, pattern=r"^(knowledge|research|journal|memory|none)$"
    )
    ui_config: dict[str, Any] = Field(default_factory=dict)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=16000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.islower():
            raise ValueError("name must be lowercase")
        return v

    @field_validator("allowed_tools")
    @classmethod
    def validate_allowed_tools(cls, v: list[str]) -> list[str]:
        # Validate tools exist in registry
        from backend.mcp.tools import TOOL_FUNCTIONS

        invalid = [t for t in v if t not in TOOL_FUNCTIONS]
        if invalid:
            raise ValueError(
                f"Unknown tools: {invalid}. Valid: {list(TOOL_FUNCTIONS.keys())}"
            )
        if len(v) > 6:
            raise ValueError("Maximum 6 tools allowed")
        return v

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, v: str) -> str:
        safety = validate_system_prompt(v)
        if not safety["is_safe"]:
            # Package first 3 warnings into validation error
            first_warnings = ", ".join(safety["warnings"][:3])
            raise ValueError(f"System prompt safety check failed: {first_warnings}")
        return v


class CustomAgentResponse(BaseModel):
    id: str
    name: str
    display_name: str | None
    tagline: str | None
    system_prompt: str
    allowed_tools: list[str]
    parent_cluster: str | None
    ui_config: dict[str, Any]
    temperature: float
    max_tokens: int
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CustomAgentListResponse(BaseModel):
    agents: list[CustomAgentResponse]
    total: int
    page: int
    page_size: int


class TestAgentRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class TestAgentResponse(BaseModel):
    events: list[dict[str, Any]]
    invocation_id: str | None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_current_user_id() -> str:
    """Placeholder for auth integration. Replace with actual user ID from JWT."""
    # TODO: Integrate real auth
    return "system"


UserId = Annotated[str, Depends(get_current_user_id)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=CustomAgentResponse, status_code=HTTPStatus.CREATED)
async def create_custom_agent(
    payload: CreateCustomAgentRequest, user_id: UserId
) -> dict[str, Any]:
    """Create a new custom agent after safety validation."""
    # Enforce agent limit per user
    count = await database.get_custom_agent_count(user_id)
    if count >= 20:
        raise CustomAgentLimitExceeded()

    # Check name uniqueness (case-insensitive)
    exists = await database.check_custom_agent_name_exists(user_id, payload.name)
    if exists:
        raise NameConflict()

    # Create agent (safety already validated via pydantic)
    agent_id = await database.create_custom_agent(
        user_id=user_id,
        name=payload.name,
        display_name=payload.display_name,
        tagline=payload.tagline,
        system_prompt=payload.system_prompt,
        allowed_tools=json.dumps(payload.allowed_tools),
        parent_cluster=payload.parent_cluster,
        ui_config=json.dumps(payload.ui_config),
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    return await database.get_custom_agent(agent_id, user_id)


@router.get("", response_model=CustomAgentListResponse)
async def list_custom_agents(
    user_id: UserId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_disabled: bool = Query(False),
) -> dict[str, Any]:
    """List paginated custom agents for user."""
    offset = (page - 1) * page_size
    agents = await database.get_custom_agents(
        user_id=user_id,
        status_filter=None if include_disabled else "enabled",
        limit=page_size,
        offset=offset,
    )

    total = await database.get_custom_agent_count(user_id)

    return {
        "agents": agents,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{agent_id}", response_model=CustomAgentResponse)
async def get_custom_agent(agent_id: str, user_id: UserId) -> dict[str, Any]:
    """Get single agent details."""
    agent = await database.get_custom_agent(agent_id, user_id)
    if not agent:
        raise AgentNotFound()
    return agent


class UpdateCustomAgentPayload(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    tagline: str | None = Field(None, max_length=200)
    system_prompt: str | None = Field(None, min_length=10, max_length=5000)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=64, le=16000)
    allowed_tools: list[str] | None = None


@router.patch("/{agent_id}", response_model=CustomAgentResponse)
async def update_custom_agent(
    agent_id: str, payload: UpdateCustomAgentPayload, user_id: UserId
) -> dict[str, Any]:
    """Update agent fields (partial). Re-validates system_prompt if changed."""
    updates = payload.model_dump(exclude_unset=True)

    # Re-validate system_prompt if being updated
    if "system_prompt" in updates:
        safety = validate_system_prompt(updates["system_prompt"])
        if not safety["is_safe"]:
            raise SystemPromptUnsafe(safety["warnings"])

    ok = await database.update_custom_agent(agent_id, user_id, **updates)
    if not ok:
        raise AgentNotFound()

    updated = await database.get_custom_agent(agent_id, user_id)
    if not updated:
        raise AgentNotFound()
    return updated


@router.delete("/{agent_id}")
async def delete_custom_agent(agent_id: str, user_id: UserId) -> dict[str, str]:
    """Soft-delete (disable) an agent."""
    ok = await database.delete_custom_agent(agent_id, user_id)
    if not ok:
        raise AgentNotFound()
    return {"status": "deleted", "agent_id": agent_id}


@router.post("/{agent_id}/test", response_model=TestAgentResponse)
async def test_custom_agent(
    agent_id: str, payload: TestAgentRequest, user_id: UserId
) -> dict[str, Any]:
    """Dry-run agent with a prompt without persisting state."""
    events: list[dict[str, Any]] = []

    invocation_id = None

    async for event in CustomAgent(agent_id=agent_id, user_id=user_id).run(
        prompt=payload.prompt, test_mode=True, enable_state_mutation=False
    ):
        if event["type"] != "end":
            # Strip large content for API response brevity
            filtered = {
                k: v for k, v in event.items() if k != "content" or len(str(v)) < 500
            }
            events.append(filtered)
        else:
            invocation_id = event.get("invocation_id")

    return {"events": events, "invocation_id": invocation_id}


# ---------------------------------------------------------------------------
# HTTP Errors (subclasses)
# ---------------------------------------------------------------------------


class NameConflict(Exception):
    def __init__(self) -> None:
        super().__init__("Agent name already exists for this user")

    @staticmethod
    def to_response() -> tuple[dict[str, Any], int]:
        return {"error": "Agent name already exists"}, HTTPStatus.CONFLICT


class AgentNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Custom agent not found")

    @staticmethod
    def to_response() -> tuple[dict[str, Any], int]:
        return {"error": "Custom agent not found"}, HTTPStatus.NOT_FOUND


class CustomAgentLimitExceeded(Exception):
    def __init__(self) -> None:
        super().__init__("User has reached maximum custom agent limit")

    @staticmethod
    def to_response() -> tuple[dict[str, Any], int]:
        return {
            "error": "Maximum 20 custom agents per user",
            "limit": 20,
        }, HTTPStatus.TOO_MANY_REQUESTS


class CustomAgentSafetyError(Exception):
    def __init__(self) -> None:
        super().__init__("System prompt safety checks failed")

    @staticmethod
    def to_response() -> tuple[dict[str, Any], int]:
        return {"error": "Safety check failed"}, HTTPStatus.BAD_REQUEST


class SystemPromptUnsafe(Exception):
    def __init__(self, warnings: list[str]) -> None:
        self.warnings = warnings
        super().__init__(f"System prompt safety check failed: {warnings}")

    def to_response(self) -> tuple[dict[str, Any], int]:
        return {
            "error": "System prompt contains unsafe patterns",
            "warnings": self.warnings,
        }, HTTPStatus.BAD_REQUEST
